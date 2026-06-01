#!/usr/bin/env node

import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEST_DIR = join(__dirname, 'test_data');
const TEST_FILE = join(TEST_DIR, 'test_translations.txt');
const EN_FILE = join(TEST_DIR, 'test_en.txt');

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

async function analyzeFile(filePath) {
  const content = await readFile(filePath, 'utf-8');
  const lines = content.split('\n').filter(l => l.trim() && l.includes('='));

  let good = 0, bad = 0, untranslated = 0;
  const problems = [];

  for (const line of lines) {
    const eq = line.indexOf('=');
    if (eq <= 0) { bad++; problems.push({ line, issue: 'No =' }); continue; }
    const orig = line.slice(0, eq);
    const trans = line.slice(eq + 1);
    if (!orig.trim()) { bad++; problems.push({ line, issue: 'Empty original' }); continue; }
    if (!trans.trim()) { bad++; problems.push({ line, issue: 'Empty translation' }); continue; }
    if (orig === trans && orig.length > 3) { untranslated++; problems.push({ line, issue: 'Untranslated' }); }
    good++;
  }

  return { total: lines.length, good, bad, untranslated, problems };
}

async function main() {
  console.log('=== Translate Analysis — Tests ===\n');

  // Setup — create test translation files in test_data
  await mkdir(TEST_DIR, { recursive: true });

  // Test 1: Normal translations
  console.log('1. Normal translations');
  await writeFile(TEST_FILE, `MAIN MENU=Главное меню
Fullscreen=Полноэкранный режим
Sprint=Спринт
Resolution Scaling=Масштабирование разрешения
`);
  let r = await analyzeFile(TEST_FILE);
  assert(r.total === 4, '4 lines parsed');
  assert(r.good === 4, '4 good');
  assert(r.bad === 0, '0 bad');
  assert(r.untranslated === 0, '0 untranslated');

  // Test 2: Untranslated strings
  console.log('\n2. Untranslated strings');
  await writeFile(TEST_FILE, `Continue=Continue
Resolution=Resolution
Help=Help
`);
  r = await analyzeFile(TEST_FILE);
  assert(r.untranslated >= 2, 'untranslated detected');
  assert(r.problems.some(p => p.issue === 'Untranslated'), 'untranslated in problems');

  // Test 3: Malformed lines
  console.log('\n3. Malformed lines');
  await writeFile(TEST_FILE, `=BadOrig
Good=Translation
NoEqualsSign
`);
  r = await analyzeFile(TEST_FILE);
  assert(r.bad >= 1, 'bad lines detected');
  assert(r.good === 1, '1 good line');

  // Test 4: Empty file
  console.log('\n4. Empty file');
  await writeFile(TEST_FILE, ``);
  r = await analyzeFile(TEST_FILE);
  assert(r.total === 0, '0 total');
  assert(r.good === 0, '0 good');

  // Test 5: Same original == translation but short
  console.log('\n5. Short same orig/trans');
  await writeFile(TEST_FILE, `ON=ON
OFF=OFF
OK=OK
`);
  r = await analyzeFile(TEST_FILE);
  assert(r.untranslated === 0, 'short not flagged as untranslated');

  // Cleanup
  try { await unlink(TEST_FILE); } catch {}
  try { await unlink(EN_FILE); } catch {}

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
