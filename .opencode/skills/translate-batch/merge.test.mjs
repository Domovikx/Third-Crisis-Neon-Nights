#!/usr/bin/env node

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

function mergeDict(obj) {
  const dict = new Map();
  let total = 0;
  for (const [orig, trans] of Object.entries(obj)) {
    total++;
    if (trans && !dict.has(orig)) dict.set(orig, trans);
  }
  return { total, count: dict.size, dict };
}

async function main() {
  console.log('=== Merge — Tests ===\n');

  // Test 1: Basic merge
  console.log('1. Basic merge');
  const d1 = { Fullscreen: 'Полный экран', Volume: 'Громкость', Hello: 'Привет', Goodbye: 'Пока' };
  const r1 = mergeDict(d1);
  assert(r1.count === 4, '4 unique');
  assert(r1.total === 4, '4 total');
  assert(r1.dict.get('Fullscreen') === 'Полный экран', 'Fullscreen');

  // Test 2: Skip untranslated
  console.log('\n2. Skip untranslated');
  const d2 = { ...d1, Sprint: '', Jump: '' };
  const r2 = mergeDict(d2);
  assert(r2.count === 4, 'still 4 (Sprint/Jump skipped)');
  assert(r2.total === 6, '6 total');

  // Test 3: Duplicate — last processed wins (JSON.parse overwrites earlier keys)
  console.log('\n3. Duplicate — last wins');
  const d3 = { ...d1, Fullscreen: 'Override' };
  const r3 = mergeDict(d3);
  assert(r3.dict.get('Fullscreen') === 'Override', 'last wins');
  assert(r3.count === 4, 'still 4');

  // Test 4: Empty
  console.log('\n4. Empty');
  const r4 = mergeDict({});
  assert(r4.count === 0, '0 from empty');
  assert(r4.total === 0, '0 total');

  // Test 5: Output format
  console.log('\n5. Output format');
  const out = JSON.stringify(Object.fromEntries(r1.dict), null, 2) + '\n';
  assert(out.includes('"Fullscreen"'), 'has key');
  assert(out.includes('"Полный экран"'), 'has value');
  assert(out.trim().startsWith('{') && out.trim().endsWith('}'), 'wraps in {}');

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
