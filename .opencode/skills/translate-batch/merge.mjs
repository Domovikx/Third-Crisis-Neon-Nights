#!/usr/bin/env node

import { readFile, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const SRC_FILE = join(GAME_DIR, 'translations', 'ru', 'NeonTranslatorRuntime_Data.json');
const OUT_FILE = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'Managed', 'NeonTranslatorRuntime_Data.json');

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');

async function main() {
  console.log('=== Deploy translations → Managed ===\n');

  const content = await readFile(SRC_FILE, 'utf-8');
  const obj = JSON.parse(content);
  const outObj = {};
  const seen = new Set();

  for (const [orig, trans] of Object.entries(obj)) {
    const key = orig.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (trans) outObj[orig] = trans;
  }

  console.log(`Unique translated: ${Object.keys(outObj).length}`);

  if (DRY_RUN) {
    console.log('\nDry run — no output written.');
    return;
  }

  const json = JSON.stringify(outObj, null, 2) + '\n';
  await writeFile(SRC_FILE, json, 'utf-8');
  await writeFile(OUT_FILE, json, 'utf-8');
  console.log(`Written: ${SRC_FILE} + ${OUT_FILE}`);
}

main().catch(console.error);
