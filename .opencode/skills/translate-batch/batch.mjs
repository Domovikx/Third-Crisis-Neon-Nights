#!/usr/bin/env node

import { readFile, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const SRC_FILE = join(GAME_DIR, 'translations', 'ru', 'NeonTranslatorRuntime_Data.json');

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');

async function translateBatch(texts) {
  if (!texts.length) return [];
  const payload = JSON.stringify([[texts.map(t => [t, 'en', 'ru', 1]), 'wt_lib']]);
  try {
    const res = await fetch('https://translate.googleapis.com/translate_a/t', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ 'f.req': payload })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data[0][0].map(r => r[0][0][5]?.[0]?.[0] || '');
  } catch (err) {
    console.error(`  Error: ${err.message}`);
    return texts.map(() => null);
  }
}

async function main() {
  console.log('=== Batch Translate ===\n' + (DRY_RUN ? '* DRY RUN *\n' : ''));

  const content = await readFile(SRC_FILE, 'utf-8');
  const dict = JSON.parse(content);

  const pending = Object.entries(dict).filter(([, v]) => !v).map(([k]) => k);
  console.log(`Untranslated: ${pending.length}`);

  if (!pending.length) { console.log('Nothing to translate.'); return; }

  const BATCH = 25;
  let done = 0, failed = 0;

  for (let i = 0; i < pending.length; i += BATCH) {
    const batch = pending.slice(i, i + BATCH);
    console.log(`Batch ${Math.floor(i / BATCH) + 1}/${Math.ceil(pending.length / BATCH)} (${batch.length})...`);

    if (!DRY_RUN) {
      const results = await translateBatch(batch);
      for (let j = 0; j < results.length; j++) {
        if (results[j]) { dict[batch[j]] = results[j]; done++; }
        else failed++;
      }
    }
    if (i + BATCH < pending.length) await new Promise(r => setTimeout(r, 1000));
  }

  if (DRY_RUN) {
    console.log(`Would translate: ${pending.length}`);
    return;
  }

  await writeFile(SRC_FILE, JSON.stringify(dict, null, 2) + '\n', 'utf-8');
  console.log(`\nDone! Translated: ${done}, Errors: ${failed}`);
}

main().catch(console.error);
