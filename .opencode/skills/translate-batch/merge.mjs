#!/usr/bin/env node

import { readFile, writeFile, readdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const TRANS_DIR = join(GAME_DIR, 'translations', 'ru');
const OUT_FILE = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'Managed', 'NeonTranslatorRuntime_Data.ndjson');

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');

async function findNDJSONFiles(dir) {
  const entries = [];
  async function walk(d) {
    const items = await readdir(d, { withFileTypes: true });
    for (const item of items) {
      const fp = join(d, item.name);
      if (item.isDirectory()) await walk(fp);
      else if (item.name.endsWith('.ndjson')) entries.push(fp);
    }
  }
  await walk(dir);
  return entries;
}

async function main() {
  console.log('=== Merge translations → Runtime dictionary ===\n');

  const files = await findNDJSONFiles(TRANS_DIR);
  if (!files.length) {
    console.error('No NDJSON files found in ' + TRANS_DIR);
    process.exit(1);
  }

  console.log(`Found ${files.length} translation files`);

  // Build flat dict: original → translated (first translated wins)
  const dict = new Map();
  let total = 0, translated = 0;

  for (const fp of files) {
    const content = await readFile(fp, 'utf-8');
    for (const line of content.trim().split('\n').filter(Boolean)) {
      try {
        const [id, orig, trans] = JSON.parse(line);
        if (!orig) continue;
        total++;
        if (trans) {
          if (!dict.has(orig)) dict.set(orig, trans);
          translated++;
        }
      } catch { /* skip bad lines */ }
    }
  }

  console.log(`Total entries: ${total}`);
  console.log(`Unique translated: ${dict.size}`);
  console.log(`Coverage: ${(dict.size / total * 100).toFixed(1)}%`);

  if (DRY_RUN) {
    console.log('\nDry run — no output written.');
    return;
  }

  // Write runtime format: ["_ag_XXXX", "original", "translated", ""]
  let seq = 1;
  const lines = [];
  for (const [orig, trans] of dict) {
    const id = `_ag_${String(seq).padStart(4, '0')}`;
    lines.push(JSON.stringify([id, orig, trans, '']));
    seq++;
  }

  await writeFile(OUT_FILE, lines.join('\n') + '\n', 'utf-8');
  console.log(`\nWritten: ${OUT_FILE} (${dict.size} translations)`);
}

main().catch(console.error);
