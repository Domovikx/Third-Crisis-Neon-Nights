#!/usr/bin/env node

import { readFile, writeFile, readdir } from 'node:fs/promises';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const TRANS_DIR = join(GAME_DIR, 'translations', 'ru');

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

async function loadExisting() {
  const files = await findNDJSONFiles(TRANS_DIR);
  const entries = []; // { file, id, original, translated, offset }

  for (const fp of files) {
    try {
      const content = await readFile(fp, 'utf-8');
      for (const line of content.trim().split('\n').filter(Boolean)) {
        try {
          const [id, orig, trans, offset] = JSON.parse(line);
          if (orig && !trans) entries.push({ file: fp, id, original: orig, offset: offset || '' });
        } catch { /* skip bad lines */ }
      }
    } catch { /* skip */ }
  }
  return entries;
}

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

  const pending = await loadExisting();
  console.log(`Files: ${new Set(pending.map(e => e.file)).size}`);
  console.log(`Untranslated: ${pending.length}`);

  if (!pending.length) { console.log('Nothing to translate.'); return; }

  const BATCH = 25;
  let done = 0, failed = 0;
  const fileUpdates = new Map(); // file → [line, ...]

  for (let i = 0; i < pending.length; i += BATCH) {
    const batch = pending.slice(i, i + BATCH);
    const texts = batch.map(e => e.original);
    console.log(`Batch ${Math.floor(i / BATCH) + 1}/${Math.ceil(pending.length / BATCH)} (${texts.length})...`);

    if (!DRY_RUN) {
      const results = await translateBatch(texts);
      for (let j = 0; j < results.length; j++) {
        const entry = batch[j];
        if (results[j]) {
          if (!fileUpdates.has(entry.file)) fileUpdates.set(entry.file, []);
          fileUpdates.get(entry.file).push({ id: entry.id, original: entry.original, translated: results[j], offset: entry.offset });
          done++;
        } else failed++;
      }
    }
    if (i + BATCH < pending.length) await new Promise(r => setTimeout(r, 1000));
  }

  if (DRY_RUN) {
    console.log(`Would translate: ${pending.length}`);
    return;
  }

  // Write updated translations back to files
  let written = 0;
  for (const [fp, updates] of fileUpdates) {
    const updateMap = new Map(updates.map(u => [u.original, u]));
    const content = await readFile(fp, 'utf-8');
    const lines = content.trim().split('\n');
    const out = lines.map(line => {
      try {
        const [id, orig, trans, offset] = JSON.parse(line);
        if (updateMap.has(orig)) {
          const u = updateMap.get(orig);
          written++;
          return JSON.stringify([u.id, u.original, u.translated, u.offset]);
        }
        return line;
      } catch { return line; }
    });
    await writeFile(fp, out.join('\n') + '\n', 'utf-8');
  }

  console.log(`\nDone! Translated: ${done}, Errors: ${failed}, Written: ${written}`);
}

main().catch(console.error);
