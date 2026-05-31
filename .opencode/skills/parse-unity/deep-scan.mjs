#!/usr/bin/env node
/**
 * deep-scan.mjs — Comprehensive string search across all game files
 *
 * Searches for target strings in every file across ALL formats:
 * 1. Null-terminated ASCII (C-strings)
 * 2. .NET US heap (length-prefixed UTF-8 + optional UTF-16LE)
 * 3. Unity aligned strings (int32 length + data)
 * 4. Raw binary substring match (any encoding)
 * 5. UTF-16LE wide strings
 * 6. Base64 encoded (unlikely but possible)
 */

import { readFile, readdir, stat } from 'node:fs/promises';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');

const TARGETS = [
  'OPTIONS', 'VIDEO', 'GAME', 'SOUND', 'CONTROLS', 'TOYS',
  'FULLSCREEN', 'RESOLUTION', 'SCALING',
  'ENVIRONMENT EFFECTS', 'REALTIME REFLECTIONS', 'REFLECTIONS',
  'POST PROCESSING', 'ENABLE VSYNC', 'VSYNC', 'FPS LIMIT',
  'NEW GAME', 'LOAD GAME', 'CONTINUE', 'MAIN MENU', 'PAUSE',
  'SETTINGS', 'LANGUAGE', 'AUDIO', 'DISPLAY', 'GRAPHICS',
  'APPLY', 'DEFAULT', 'CANCEL', 'SAVE', 'QUIT', 'EXIT',
  'DIFFICULTY', 'VOLUME', 'MASTER', 'MUSIC', 'SFX', 'VOICE',
  'BRIGHTNESS', 'QUALITY', 'LOW', 'MEDIUM', 'HIGH', 'ULTRA',
  'WINDOWED', 'BORDERLESS', 'EXCLUSIVE', 'FULLSCREEN MODE',
  'RESOLUTION SCALING', 'ENVIRONMENT EFFECTS',
  'REALTIME REFLECTIONS', 'POST PROCESSING',
  'ENABLE VSYNC', 'FPS LIMIT',
  'BACK', 'OPTIONS MENU', 'VIDEO SETTINGS', 'GAME SETTINGS',
  'SOUND SETTINGS', 'CONTROLS SETTINGS', 'TOYS SETTINGS',
];

// ====== Search strategies ======

function searchNullTerminated(buf, target) {
  const indices = [];
  let pos = -1;
  while ((pos = buf.indexOf(target, pos + 1)) !== -1) {
    // Check if null-terminated (byte after target is 0 or end of buffer)
    const after = buf[pos + target.length];
    if (after === 0 || after === undefined) {
      indices.push(pos);
    }
  }
  return indices;
}

function searchRaw(buf, target) {
  const indices = [];
  let pos = -1;
  while ((pos = buf.indexOf(target, pos + 1)) !== -1) {
    indices.push(pos);
  }
  return indices;
}

function searchLengthPrefixed(buf, target) {
  const indices = [];
  const len = target.length;
  // .NET US heap: length byte(s) include null terminator
  // Simple case: single byte length = target.length + 1
  const netLen = len + 1;
  if (netLen < 128) {
    const needle = Buffer.alloc(1 + len + 1);
    needle[0] = netLen;
    needle.write(target, 1, 'utf-8');
    needle[1 + len] = 0;
    let pos = -1;
    while ((pos = buf.indexOf(needle, pos + 1)) !== -1) indices.push(pos);
  }

  // Unity aligned string: int32 LE length
  const unityNeedle = Buffer.alloc(4 + len);
  unityNeedle.writeUInt32LE(len, 0);
  unityNeedle.write(target, 4, 'utf-8');
  let pos = -1;
  while ((pos = buf.indexOf(unityNeedle, pos + 1)) !== -1) indices.push(pos);

  return indices;
}

function searchUTF16LE(buf, target) {
  const indices = [];
  // Convert target to UTF-16LE
  const u16 = Buffer.alloc(target.length * 2);
  for (let i = 0; i < target.length; i++) {
    u16.writeUInt16LE(target.charCodeAt(i), i * 2);
  }
  let pos = -1;
  while ((pos = buf.indexOf(u16, pos + 1)) !== -1) indices.push(pos);
  return indices;
}

function searchUTF16LENull(buf, target) {
  const indices = [];
  const u16 = Buffer.alloc(target.length * 2 + 2);
  for (let i = 0; i < target.length; i++) {
    u16.writeUInt16LE(target.charCodeAt(i), i * 2);
  }
  u16[target.length * 2] = 0;
  u16[target.length * 2 + 1] = 0;
  let pos = -1;
  while ((pos = buf.indexOf(u16, pos + 1)) !== -1) indices.push(pos);
  return indices;
}

function searchUSHeapUTF16(buf, target) {
  // .NET #US heap stores strings as: byte_count (compressed) + UTF-16LE data
  // byte_count includes the null terminator (2 bytes for UTF-16LE)
  const indices = [];
  const byteLen = target.length * 2 + 2; // chars * 2 + null terminator
  if (byteLen < 128) {
    const needle = Buffer.alloc(1 + byteLen);
    needle[0] = byteLen;
    for (let i = 0; i < target.length; i++) {
      needle.writeUInt16LE(target.charCodeAt(i), 1 + i * 2);
    }
    // null terminator already zeroed
    let pos = -1;
    while ((pos = buf.indexOf(needle, pos + 1)) !== -1) indices.push(pos);
  }
  return indices;
}

// ====== File scanning ======

async function* walkFiles(dir, depth = 0) {
  if (depth > 5) return;
  try {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const fp = join(dir, e.name);
      if (e.name === '.git' || e.name === 'output') continue;
      if (e.isDirectory()) {
        yield* walkFiles(fp, depth + 1);
      } else if (e.isFile()) {
        yield fp;
      }
    }
  } catch {}
}

// ====== Main ======

async function main() {
  console.log('=== Deep scan: searching all game files for UI strings ===\n');

  const results = {}; // target → { file, offset, method }[]

  let filesScanned = 0;
  const maxSize = 100 * 1024 * 1024; // 100MB

  // Focus only on bundles (97 files) + .assets files
  const bundleDir = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'StreamingAssets', 'aa', 'StandaloneWindows64');
  const bundleFiles = (await readdir(bundleDir)).filter(f => f.endsWith('.bundle'));
  for (const bf of bundleFiles) {
    const fp = join(bundleDir, bf);
    const st = await stat(fp).catch(() => null);
    if (!st || !st.isFile() || st.size > maxSize) continue;
    const name = bf;

    const buf = await readFile(fp).catch(() => null);
    if (!buf) continue;

    filesScanned++;

    for (const target of TARGETS) {
      const found = [];
      const raw = searchRaw(buf, target);
      if (raw.length > 0) found.push(...raw.map(o => ({ offset: o, method: 'raw' })));
      const u16 = searchUTF16LE(buf, target);
      if (u16.length > 0) found.push(...u16.map(o => ({ offset: o, method: 'utf16le' })));
      const u16n = searchUTF16LENull(buf, target);
      if (u16n.length > 0) found.push(...u16n.map(o => ({ offset: o, method: 'utf16le_null' })));
      const lp = searchLengthPrefixed(buf, target);
      if (lp.length > 0) found.push(...lp.map(o => ({ offset: o, method: 'len_prefixed' })));
      const ush = searchUSHeapUTF16(buf, target);
      if (ush.length > 0) found.push(...ush.map(o => ({ offset: o, method: 'us_heap_utf16' })));

      if (found.length > 0) {
        if (!results[target]) results[target] = [];
        for (const f of found) {
          results[target].push({ file: fp.replace(GAME_DIR, '').replace(/^[/\\]/, ''), offset: f.offset, method: f.method });
        }
      }
    }

    if (filesScanned % 25 === 0) process.stderr.write('.');
  }

  console.log(`\nFiles scanned: ${filesScanned}\n`);

  // Report
  for (const target of TARGETS) {
    const hits = results[target];
    if (!hits || hits.length === 0) {
      console.log(`❌ ${target}: NOT FOUND`);
      continue;
    }
    // Group by file
    const byFile = {};
    for (const h of hits) {
      const file = h.file.replace(GAME_DIR, '').replace(/^[/\\]/, '');
      if (!byFile[file]) byFile[file] = new Set();
      byFile[file].add(h.offset);
    }
    console.log(`✅ ${target}:`);
    for (const [file, offsets] of Object.entries(byFile)) {
      const offs = [...offsets].sort((a, b) => a - b);
      console.log(`     ${file} (${offs.length}x) @ ${offs.slice(0, 5).map(o => '0x' + o.toString(16)).join(', ')}${offs.length > 5 ? '...' : ''}`);
    }
  }
}

main().catch(console.error);
