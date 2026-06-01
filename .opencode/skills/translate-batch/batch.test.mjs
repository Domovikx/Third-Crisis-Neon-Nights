#!/usr/bin/env node

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEST_DIR = join(__dirname, 'test_data');

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

// Minimal reimplementation of batch logic for testing
async function findUntranslated(dir) {
  const { readdir } = await import('node:fs/promises');
  const { join } = await import('node:path');
  const entries = [];
  async function walk(d) {
    const items = await readdir(d, { withFileTypes: true });
    for (const item of items) {
      const fp = join(d, item.name);
      if (item.isDirectory()) await walk(fp);
      else if (item.name.endsWith('.ndjson')) {
        const content = await readFile(fp, 'utf-8');
        for (const line of content.trim().split('\n').filter(Boolean)) {
          try {
            const [id, orig, trans] = JSON.parse(line);
            if (orig && !trans) entries.push({ file: fp, id, original: orig });
          } catch {}
        }
      }
    }
  }
  await walk(dir);
  return entries;
}

async function injectTranslations(dir, updates) {
  const { readdir, writeFile } = await import('node:fs/promises');
  const { join } = await import('node:path');
  const updateMap = new Map(updates.map(u => [u.original, u.translated]));
  let written = 0;

  async function walk(d) {
    const items = await readdir(d, { withFileTypes: true });
    for (const item of items) {
      const fp = join(d, item.name);
      if (item.isDirectory()) await walk(fp);
      else if (item.name.endsWith('.ndjson')) {
        const content = await readFile(fp, 'utf-8');
        const lines = content.trim().split('\n');
        const out = lines.map(line => {
          try {
            const [id, orig, trans, offset] = JSON.parse(line);
            if (updateMap.has(orig)) {
              written++;
              return JSON.stringify([id, orig, updateMap.get(orig), offset || '']);
            }
            return line;
          } catch { return line; }
        });
        await writeFile(fp, out.join('\n') + '\n', 'utf-8');
      }
    }
  }
  await walk(dir);
  return written;
}

async function main() {
  console.log('=== Batch Translate — Tests ===\n');

  // Clean start
  const { rm } = await import('node:fs/promises');
  await rm(TEST_DIR, { recursive: true, force: true });
  await mkdir(TEST_DIR, { recursive: true });
  const uiDir = join(TEST_DIR, 'ui');
  const dialogsDir = join(TEST_DIR, 'dialogs');
  await mkdir(uiDir, { recursive: true });
  await mkdir(dialogsDir, { recursive: true });

  // Test 1: findUntranslated — finds only entries with empty 3rd field
  console.log('1. findUntranslated');
  await writeFile(join(uiDir, 'test.ndjson'), [
    JSON.stringify(['t_001', 'Sprint', '', '100']),
    JSON.stringify(['t_002', 'Cancel', 'Отмена', '200']),
    JSON.stringify(['t_003', 'Jump', '', '300']),
  ].join('\n') + '\n', 'utf-8');

  const untranslated = await findUntranslated(TEST_DIR);
  assert(untranslated.length === 2, '2 untranslated found');
  assert(untranslated.some(e => e.original === 'Sprint'), 'Sprint is untranslated');
  assert(untranslated.some(e => e.original === 'Jump'), 'Jump is untranslated');
  assert(!untranslated.some(e => e.original === 'Cancel'), 'Cancel is translated');

  // Test 2: Inject translations
  console.log('\n2. injectTranslations');
  const injected = await injectTranslations(TEST_DIR, [
    { original: 'Sprint', translated: 'Спринт' },
    { original: 'Jump', translated: 'Прыжок' },
  ]);
  assert(injected === 2, '2 translations injected');

  const remaining = await findUntranslated(TEST_DIR);
  assert(remaining.length === 0, '0 remaining untranslated');

  // Test 3: Batch only processes untranslated — Cancel is already translated
  console.log('\n3. Already translated entries ignored by findUntranslated');
  const shouldNotFindCancel = untranslated.some(e => e.original === 'Cancel');
  assert(!shouldNotFindCancel, 'already translated Cancel not in untranslated list');
  assert(untranslated.length === 2, 'exactly 2 untranslated (Sprint, Jump)');

  // Test 4: Multiple files in subdirectories
  console.log('\n4. Multiple subdirectories');
  await writeFile(join(dialogsDir, 'dialogue.ndjson'), [
    JSON.stringify(['d_001', 'Hello world', '', '500']),
    JSON.stringify(['d_002', 'Good morning', '', '600']),
  ].join('\n') + '\n', 'utf-8');

  const allUntranslated = await findUntranslated(TEST_DIR);
  assert(allUntranslated.length === 2, '2 untranslated from dialogs dir');
  assert(allUntranslated.every(e => e.file.includes('dialogue.ndjson')), 'both from dialog file');

  // Test 5: Empty file safety
  console.log('\n5. Empty file safety');
  await writeFile(join(TEST_DIR, 'empty.ndjson'), '', 'utf-8');
  const emptyResult = await findUntranslated(TEST_DIR);
  assert(emptyResult.length === 2, 'ignores empty file, still 2');

  // Cleanup
  await rm(TEST_DIR, { recursive: true, force: true });

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
