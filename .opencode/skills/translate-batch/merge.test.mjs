#!/usr/bin/env node

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function mergeFromDir(dir) {
  const { readdir } = await import('node:fs/promises');
  const files = [];
  async function walk(d) {
    const items = await readdir(d, { withFileTypes: true });
    for (const item of items) {
      const fp = join(d, item.name);
      if (item.isDirectory()) await walk(fp);
      else if (item.name.endsWith('.ndjson')) files.push(fp);
    }
  }
  await walk(dir);
  const dict = new Map();
  let total = 0;
  for (const fp of files) {
    const content = await readFile(fp, 'utf-8');
    for (const line of content.trim().split('\n').filter(Boolean)) {
      try {
        const [id, orig, trans] = JSON.parse(line);
        if (!orig) continue;
        total++;
        if (trans && !dict.has(orig)) dict.set(orig, trans);
      } catch {}
    }
  }
  return { total, dict, count: dict.size };
}

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

async function main() {
  console.log('=== Merge — Tests ===\n');

  const tmp = join(__dirname, 'test_merge_tmp');

  // Clean start — remove entire tmp first
  try { const { rm } = await import('node:fs/promises'); await rm(tmp, { recursive: true, force: true }); } catch {}

  const uiDir = join(tmp, 'ui');
  const dialogsDir = join(tmp, 'dialogs');
  await mkdir(uiDir, { recursive: true });
  await mkdir(dialogsDir, { recursive: true });

  // Test 1: Basic merge across dirs
  console.log('1. Basic merge across dirs');
  await writeFile(join(uiDir, 'settings.ndjson'), [
    JSON.stringify(['u_001', 'Fullscreen', 'Полный экран', '100']),
    JSON.stringify(['u_002', 'Volume', 'Громкость', '200']),
  ].join('\n') + '\n', 'utf-8');
  await writeFile(join(dialogsDir, 'scene1.ndjson'), [
    JSON.stringify(['d_001', 'Hello', 'Привет', '300']),
    JSON.stringify(['d_002', 'Goodbye', 'Пока', '400']),
  ].join('\n') + '\n', 'utf-8');

  const r1 = await mergeFromDir(tmp);
  assert(r1.count === 4, '4 unique translations');
  assert(r1.total === 4, '4 total entries');
  assert(r1.dict.get('Fullscreen') === 'Полный экран', 'Fullscreen translated');
  assert(r1.dict.get('Hello') === 'Привет', 'Hello translated');

  // Test 2: Skip untranslated entries
  console.log('\n2. Skip untranslated');
  await writeFile(join(uiDir, 'untranslated.ndjson'), [
    JSON.stringify(['u_003', 'Sprint', '', '500']),
    JSON.stringify(['u_004', 'Jump', '', '600']),
  ].join('\n') + '\n', 'utf-8');

  const r2 = await mergeFromDir(tmp);
  assert(r2.count === 4, 'still 4 unique (Sprint and Jump skipped)');
  assert(r2.total === 6, '6 total entries (2 untranslated counted)');

  // Test 3: Duplicate original — already in dict, skipped
  console.log('\n3. Duplicate original — already in dict');
  await writeFile(join(tmp, 'dupes.ndjson'), [
    JSON.stringify(['o_001', 'Fullscreen', 'OVERRIDE', '999']),
    JSON.stringify(['o_002', 'Fullscreen', 'ALSO_OVER', '998']),
  ].join('\n') + '\n', 'utf-8');

  const r3 = await mergeFromDir(tmp);
  assert(r3.count === 4, '4 unique (Fullscreen already in dict, skip dupes)');
  assert(r3.total === 8, '8 total entries (6 prev + 2 dupes)');
  assert(r3.dict.has('Fullscreen'), 'Fullscreen still present');

  // Test 4: Empty file safety
  console.log('\n4. Empty file safety');
  await writeFile(join(tmp, 'empty.ndjson'), '', 'utf-8');
  const r4 = await mergeFromDir(tmp);
  assert(r4.count === 4, 'still 4 after empty file');
  assert(r4.total === 8, 'still 8 total after empty file');

  // Test 5: Output format
  console.log('\n5. Output format');
  let seq = 1;
  const lines = [];
  for (const [orig, trans] of r4.dict) {
    const id = `_ag_${String(seq).padStart(4, '0')}`;
    lines.push(JSON.stringify([id, orig, trans, '']));
    seq++;
  }
  const first = lines[0];
  assert(first.startsWith('["_ag_0001"'), 'sequential _ag_XXXX ids');
  assert(seq - 1 === 4, '4 total output lines (matching unique count)');

  // Cleanup
  const { rm } = await import('node:fs/promises');
  await rm(tmp, { recursive: true, force: true });

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
