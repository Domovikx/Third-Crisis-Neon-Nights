#!/usr/bin/env node

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const DATA_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data');
const OUT_DIR = join(GAME_DIR, 'output', 'raw');

// ====== Header parsing ======
function parseHeader(buf) {
  const isNewFormat = buf[0] === 0 && buf[1] === 0 && buf[2] === 0 && buf[3] === 0
    && buf[4] === 0 && buf[5] === 0 && buf[6] === 0 && buf[7] === 0;

  if (!isNewFormat) {
    const metadataSize = buf.readUInt32LE(0);
    const fileSize = buf.readUInt32LE(4);
    const version = buf.readUInt32LE(8);
    const dataOffset = buf.readUInt32LE(12);
    const endian = buf[16];
    return { version, dataOffset, metadataSize, fileSize, endianess: endian,
      bigEndian: endian === 1, headerSize: 20, metadataOffset: 20,
      unityVersion: 'pre-2020', newFormat: false };
  }

  // New format (Unity 2020+): bytes 0-7 zeros, rest BE
  const version = buf.readInt32BE(8);
  const endian = buf[16];
  const metadataSize = buf.readInt32BE(20);
  const fileSize = buf.readInt32BE(28);
  const dataOffset = buf.readInt32BE(36);
  const metadataOffset = dataOffset - metadataSize;

  // Unity version is at bytes 48-59 (padded to 4)
  let verEnd = 48;
  while (buf[verEnd] !== 0) verEnd++;
  const unityVersion = buf.toString('utf-8', 48, verEnd);

  return { version, dataOffset, metadataSize, fileSize,
    endianess: endian, bigEndian: endian === 1,
    headerSize: metadataOffset, metadataOffset,
    unityVersion, newFormat: true };
}

// ====== String extraction from data section ======
function extractStrings(buf, dataOffset) {
  const dataBuf = buf.slice(dataOffset);
  const strings = [];

  // Scan for null-terminated ASCII strings (C-strings)
  let cur = '';
  for (let i = 0; i < dataBuf.length; i++) {
    const b = dataBuf[i];
    if (b >= 32 && b <= 126) {
      cur += String.fromCharCode(b);
    } else {
      if (cur.length >= 8 && cur.length <= 500) {
        const letters = (cur.match(/[a-zA-Z]/g) || []).length;
        if (letters >= cur.length * 0.4) {
          strings.push(cur.trim());
        }
      }
      cur = '';
    }
  }

  return strings;
}

// ====== Dialogue detection ======
const NOISE_SET = new Set([
  'hotel', 'room', 'floor', 'wall', 'door', 'pack', 'camera', 'light',
  'collider', 'audio', 'sprite', 'mesh', 'shader', 'material', 'texture',
  'canvas', 'panel', 'button', 'image', 'text', 'input', 'scroll', 'slider',
  'toggle', 'dropdown', 'animator', 'rig', 'bone', 'blend', 'clip',
  'navmesh', 'pathfinding', 'grid', 'layout', 'content', 'mask',
  'particle', 'trail', 'line', 'effect', 'postprocess', 'volume',
  'profile', 'asset', 'bundle', 'addressable', 'resource',
  'instance', 'prefab', 'variant', 'copy', 'clone',
]);

const COMMON_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
  'my', 'your', 'his', 'its', 'our', 'their',
  'this', 'that', 'these', 'those',
  'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'of', 'about',
  'and', 'or', 'but', 'if', 'because', 'so', 'while',
  'what', 'where', 'when', 'why', 'how', 'who', 'which',
  'do', 'does', 'did', 'done', 'doing',
  'have', 'has', 'had', 'having',
  'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must',
  'get', 'got', 'gotten', 'take', 'took', 'taken',
  'know', 'knew', 'known', 'think', 'thought',
  'want', 'need', 'like', 'look', 'see', 'saw', 'go', 'went', 'gone',
  'come', 'came', 'make', 'made', 'say', 'said', 'tell', 'told',
  'yes', 'no', 'ok', 'okay', 'please', 'thanks', 'thank',
  'not', 'no', 'don\'t', 'doesn\'t', 'didn\'t', 'won\'t', 'wouldn\'t',
  'can\'t', 'couldn\'t', 'shouldn\'t', 'isn\'t', 'aren\'t', 'wasn\'t',
  'weren\'t', 'haven\'t', 'hasn\'t', 'hadn\'t', 'ain\'t',
  'im', 'youre', 'hes', 'shes', 'its', 'we\'re', 'they\'re',
  'ive', 'you\'ve', 'we\'ve', 'they\'ve',
  'well', 'ill', 'youll', 'lets',
]);

function isDialogue(str) {
  if (str.length < 12 || str.length > 500) return false;
  if (str.includes('_')) return false;
  if (str.includes('/')) return false;
  if (/\.\w{2,4}$/.test(str)) return false;

  const words = str.toLowerCase().split(/\s+/);
  if (words.length < 3) return false;

  const alpha = (str.match(/[a-zA-Z]/g) || []).length;
  const lower = (str.match(/[a-z]/g) || []).length;
  if (alpha < 5 || lower < 3) return false;
  if (alpha / str.length < 0.35) return false;

  // Has common English words?
  const commonCount = words.filter(w => COMMON_WORDS.has(w.replace(/[^a-z']/g, ''))).length;
  if (commonCount === 0 && !/[a-z][A-Z]/.test(str)) return false;

  // Check if starts with known noise words
  const firstWord = words[0].replace(/[^a-z]/g, '');
  if (firstWord.length > 0 && NOISE_SET.has(firstWord)) return false;

  // Reject "(number)" at end
  if (/\(\d+\)$/.test(str.trim())) return false;

  // Reject strings with minimal lowercase (likely object names)
  const uppercaseRatio = alpha > 0 ? (str.match(/[A-Z]/g) || []).length / alpha : 0;
  if (uppercaseRatio > 0.8 && lower < alpha * 0.5) return false;

  return true;
}

function isUI(str) {
  const s = str.trim();
  if (s.length < 2 || s.length > 60) return false;
  if (!/^[A-Z0-9\s\-\.\,\!\?\'\"\:]{2,60}$/.test(s)) return false;
  const letters = (s.match(/[A-Z]/g) || []).length;
  return letters >= 2;
}

// ====== Main ======
async function main() {
  const args = process.argv.slice(2);
  const specificLevel = args.includes('--level') ? parseInt(args[args.indexOf('--level') + 1]) : null;
  const minLen = parseInt(args.includes('--min') ? args[args.indexOf('--min') + 1] : '10', 10);
  const detailed = args.includes('--detailed');
  const jsonOutput = args.includes('--json');

  const files = [];
  if (specificLevel !== null) {
    files.push({ name: `level${specificLevel}`, path: join(DATA_DIR, `level${specificLevel}`) });
  } else {
    for (let i = 0; i <= 15; i++)
      files.push({ name: `level${i}`, path: join(DATA_DIR, `level${i}`) });
    files.push({ name: 'sharedassets0', path: join(DATA_DIR, 'sharedassets0.assets') });
  }

  let allDialogue = [];
  let allUI = [];

  console.log('=== Unity Serialized Parser v3 ===\n');

  for (const { name, path: fp } of files) {
    try {
      const buf = await readFile(fp);
      const header = parseHeader(buf);

      console.log(`${name}:`);
      console.log(`  v${header.version} | ${(header.fileSize / 1024 / 1024).toFixed(2)} MB | Data: ${((header.fileSize - header.dataOffset) / 1024 / 1024).toFixed(2)} MB`);

      const strings = extractStrings(buf, header.dataOffset);
      const filtered = strings.filter(s => s.length >= minLen);

      let dialogue = [];
      let ui = [];
      for (const s of filtered) {
        if (isDialogue(s)) dialogue.push(s);
        else if (isUI(s)) ui.push(s);
      }

      allDialogue.push(...dialogue);
      allUI.push(...ui);

      console.log(`  Строк: ${filtered.length} → диалог:${dialogue.length}, UI:${ui.length}`);

      if (detailed && dialogue.length > 0) {
        console.log(`  Примеры:`);
        for (const s of dialogue.slice(0, 5)) console.log(`    ${s}`);
      }
    } catch (err) {
      console.log(`${name}: ОШИБКА - ${err.message}`);
    }
  }

  const uniqueDialogue = [...new Set(allDialogue)].sort();
  const uniqueUI = [...new Set(allUI)].sort();

  console.log(`\n=== ИТОГ ===`);
  console.log(`Диалогов: ${uniqueDialogue.length}`);
  console.log(`UI: ${uniqueUI.length}`);

  await mkdir(OUT_DIR, { recursive: true });
  await writeFile(join(OUT_DIR, 'parsed-all.txt'), [...uniqueDialogue, ...uniqueUI].join('\n'), 'utf-8');
  await writeFile(join(OUT_DIR, 'parsed-dialogue.txt'), uniqueDialogue.join('\n'), 'utf-8');
  await writeFile(join(OUT_DIR, 'parsed-ui.txt'), uniqueUI.join('\n'), 'utf-8');

  if (jsonOutput) {
    await writeFile(join(OUT_DIR, 'parsed.json'), JSON.stringify({
      dialogue: uniqueDialogue, ui: uniqueUI,
      stats: { dialogue: uniqueDialogue.length, ui: uniqueUI.length },
    }, null, 2), 'utf-8');
  }

  console.log(`\nСохранено в ${OUT_DIR}/`);

  if (detailed) {
    console.log(`\n=== Примеры диалогов (30) ===`);
    for (const s of uniqueDialogue.slice(0, 30)) console.log(`  ${s}`);
  }
}

main().catch(console.error);
