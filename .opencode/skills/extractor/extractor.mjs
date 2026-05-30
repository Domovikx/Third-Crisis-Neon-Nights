#!/usr/bin/env node
/**
 * extractor.mjs — Classifies and filters parsed strings
 *
 * Takes JSON from parser, applies heuristics to separate
 * dialogue from UI strings from noise (FSM state names, object names, etc.)
 *
 * Uses NOISE_SET, COMMON_WORDS word lists and structural heuristics.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');

// ====== Noise / filter data ======

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

// ====== Classification ======

export function isDialogue(str) {
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

  const commonCount = words.filter(w => COMMON_WORDS.has(w.replace(/[^a-z']/g, ''))).length;
  if (commonCount === 0 && !/[a-z][A-Z]/.test(str)) return false;

  const firstWord = words[0].replace(/[^a-z]/g, '');
  if (firstWord.length > 0 && NOISE_SET.has(firstWord)) return false;

  if (/\(\d+\)$/.test(str.trim())) return false;

  const uppercaseRatio = alpha > 0 ? (str.match(/[A-Z]/g) || []).length / alpha : 0;
  if (uppercaseRatio > 0.8 && lower < alpha * 0.5) return false;

  return true;
}

export function isUI(str) {
  const s = str.trim();
  if (s.length < 2 || s.length > 60) return false;
  if (!/^[A-Z0-9\s\-\.\,\!\?\'\"\:]{2,60}$/.test(s)) return false;
  const letters = (s.match(/[A-Z]/g) || []).length;
  return letters >= 2;
}

/**
 * Classify a single string.
 * Returns 'dialogue', 'ui', or 'noise'.
 */
export function classify(str) {
  if (isDialogue(str)) return 'dialogue';
  if (isUI(str)) return 'ui';
  return 'noise';
}

// ====== Extraction ======

export function extractStrings(parsedJson, options = {}) {
  const { minLength = 10 } = options;
  const result = {
    dialogs: {},   // { file: [ {id, raw, offset}, ... ] }
    ui: {},
    noise: {},
    stats: { dialogue: 0, ui: 0, noise: 0 },
  };

  for (const file of parsedJson.files || []) {
    const fname = file.name;

    for (const s of file.strings || []) {
      if (s.raw.length < minLength) continue;
      const cls = classify(s.raw);

      if (cls === 'dialogue') {
        if (!result.dialogs[fname]) result.dialogs[fname] = [];
        result.dialogs[fname].push({ raw: s.raw, offset: s.offset });
      } else if (cls === 'ui') {
        if (!result.ui[fname]) result.ui[fname] = [];
        result.ui[fname].push({ raw: s.raw, offset: s.offset });
      } else {
        if (!result.noise[fname]) result.noise[fname] = [];
        result.noise[fname].push({ raw: s.raw, offset: s.offset });
      }
    }
  }

  // Sort each group by offset (preserves file order)
  for (const g of [result.dialogs, result.ui, result.noise]) {
    for (const arr of Object.values(g)) {
      arr.sort((a, b) => a.offset - b.offset);
    }
  }

  result.stats.dialogue = Object.values(result.dialogs).reduce((s, a) => s + a.length, 0);
  result.stats.ui = Object.values(result.ui).reduce((s, a) => s + a.length, 0);
  result.stats.noise = Object.values(result.noise).reduce((s, a) => s + a.length, 0);
  result.stats.total = result.stats.dialogue + result.stats.ui + result.stats.noise;

  return result;
}

/**
 * Write NDJSON lines per source file.
 *
 * Format per line: ["{source}_{seq}","{original}","","{offset}"]
 *
 * @param {object} groups  { sourceName: [ {raw, offset}, ... ] }
 * @param {string} outDir  output/dir/
 * @param {string} category 'dialogs' or 'ui'
 */
async function writeNDJSON(groups, outDir, category) {
  const dir = join(outDir, category);
  await mkdir(dir, { recursive: true });

  let total = 0;
  for (const [source, entries] of Object.entries(groups)) {
    if (entries.length === 0) continue;
    const lines = entries.map((e, i) => {
      const seq = String(i + 1).padStart(3, '0');
      const id = `${source}_${seq}`;
      return JSON.stringify([id, e.raw, '', String(e.offset)]);
    });
    const fp = join(dir, `${source}.ndjson`);
    await writeFile(fp, lines.join('\n') + '\n', 'utf-8');
    total += entries.length;
  }
  return total;
}

// ====== NDJSON reader ======

/**
 * Read NDJSON lines from a file.
 * Parser format: [offset, "raw"]
 */
async function readNDJSON(filepath) {
  const text = await readFile(filepath, 'utf-8');
  const lines = text.trim().split('\n').filter(Boolean);
  const strings = [];
  for (const line of lines) {
    try {
      const [offset, raw] = JSON.parse(line);
      strings.push({ offset, raw });
    } catch {
      // skip bad lines
    }
  }
  return strings;
}

// ====== CLI ======

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`Usage: node extractor.mjs [options]

Options:
  --input-dir <dir> Input NDJSON dir from parser (default: output/parser/)
  --out <dir>       Output directory (default: output/extractor/)
  --min-len <N>     Minimum string length (default: 10)
  --detailed        Show per-file breakdown + samples
  --show-noise      Include noise strings in output
  --help, -h        Show this help

Output:
  dialogs/*.ndjson   — NDJSON: ["id","original","","offset"]
  ui/*.ndjson        — same format
`);
    return;
  }

  const inputDir = args.includes('--input-dir')
    ? args[args.indexOf('--input-dir') + 1]
    : join(GAME_DIR, 'output', 'parser');

  const outDir = args.includes('--out')
    ? args[args.indexOf('--out') + 1]
    : join(GAME_DIR, 'output', 'extractor');

  const minLength = parseInt(args.includes('--min-len') ? args[args.indexOf('--min-len') + 1] : '10', 10);
  const detailed = args.includes('--detailed');
  const showNoise = args.includes('--show-noise');

  // Read manifest
  let manifest;
  try {
    manifest = JSON.parse(await readFile(join(inputDir, 'manifest.json'), 'utf-8'));
  } catch (err) {
    console.error(`Cannot read manifest: ${err.message}`);
    console.error('Run parser.mjs first to generate NDJSON files');
    process.exit(1);
  }

  // Read all NDJSON files from parser output
  const files = [];
  for (const f of manifest.files) {
    const ndjsonPath = join(inputDir, `${f.name}.ndjson`);
    try {
      const strings = await readNDJSON(ndjsonPath);
      files.push({ name: f.name, strings });
    } catch {
      console.error(`  warn: ${f.name}.ndjson not found, skipping`);
    }
  }

  // Build input structure matching old API
  const input = { files, totalStrings: manifest.totalStrings, totalFiles: files.length };

  console.error(`Extractor: processing ${input.totalStrings} strings from ${input.totalFiles} files\n`);

  const extracted = extractStrings(input, { minLength, detailed });

  console.error(`Dialogue: ${extracted.stats.dialogue}`);
  console.error(`UI:       ${extracted.stats.ui}`);
  console.error(`Noise:    ${extracted.stats.noise}`);
  console.error(`Total:    ${extracted.stats.total}`);
  console.error(`Filtered out: ${input.totalStrings - extracted.stats.total}`);

  // Write NDJSON per source file
  await mkdir(outDir, { recursive: true });

  const dialogCount = await writeNDJSON(extracted.dialogs, outDir, 'dialogs');
  const uiCount = await writeNDJSON(extracted.ui, outDir, 'ui');

  if (showNoise) {
    const noiseCount = await writeNDJSON(extracted.noise, outDir, 'noise');
    console.error(`\nNoise files in ${outDir}/noise/`);
  }

  console.error(`\nSaved to ${outDir}/`);
  console.error(`  dialogs/: ${dialogCount} strings in ${Object.keys(extracted.dialogs).length} files`);
  console.error(`  ui/:      ${uiCount} strings in ${Object.keys(extracted.ui).length} files`);

  if (detailed) {
    // Show per-file breakdown
    console.error(`\nDialogs per file:`);
    for (const [src, arr] of Object.entries(extracted.dialogs).sort()) {
      console.error(`  ${src}.ndjson: ${arr.length}`);
    }
    console.error(`\nUI per file:`);
    for (const [src, arr] of Object.entries(extracted.ui).sort()) {
      console.error(`  ${src}.ndjson: ${arr.length}`);
    }

    if (extracted.stats.dialogue > 0) {
      console.error(`\nSample dialogue (10):`);
      const all = Object.entries(extracted.dialogs).flatMap(([f, arr]) =>
        arr.map(s => ({ file: f, ...s }))
      );
      for (const s of all.slice(0, 10)) {
        console.error(`  [${s.file}] ${s.raw}`);
      }
    }
  }
}

main().catch(console.error);
