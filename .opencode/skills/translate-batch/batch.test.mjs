#!/usr/bin/env node

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

function findUntranslated(dict) {
  return Object.entries(dict).filter(([, v]) => !v).map(([k]) => k);
}

function injectTranslations(dict, updates) {
  for (const { original, translated } of updates) {
    if (typeof dict[original] === 'string' && dict[original] === '') {
      dict[original] = translated;
    }
  }
  return dict;
}

async function main() {
  console.log('=== Batch Translate — Tests ===\n');

  // Test 1: findUntranslated
  console.log('1. findUntranslated');
  const d1 = { Sprint: '', Cancel: 'Отмена', Jump: '' };
  const r1 = findUntranslated(d1);
  assert(r1.length === 2, '2 untranslated');
  assert(r1.includes('Sprint'), 'Sprint is untranslated');
  assert(!r1.includes('Cancel'), 'Cancel is translated');

  // Test 2: injectTranslations
  console.log('\n2. injectTranslations');
  const d2 = injectTranslations({ ...d1 }, [
    { original: 'Sprint', translated: 'Спринт' },
    { original: 'Jump', translated: 'Прыжок' },
  ]);
  const r2 = findUntranslated(d2);
  assert(r2.length === 0, '0 remaining');

  // Test 3: Already translated unchanged
  console.log('\n3. Already translated unchanged');
  assert(d2.Cancel === 'Отмена', 'Cancel stays');
  assert(d2.Sprint === 'Спринт', 'Sprint updated');

  // Test 4: Empty dict
  console.log('\n4. Empty dict');
  const r4 = findUntranslated({});
  assert(r4.length === 0, 'empty = 0');

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
