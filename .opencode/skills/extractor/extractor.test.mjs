#!/usr/bin/env node

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { isDialogue, isUI, classify, extractStrings } from './extractor.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

async function main() {
  console.log('=== Extractor — Classification Tests ===\n');

  // Test 1: isDialogue
  console.log('1. isDialogue');
  assert(isDialogue('And now hold still I\'m not done yet.'), 'long sentence with contractions');
  assert(isDialogue('Hey, are you okay?'), 'short question');
  assert(isDialogue('I can\'t believe this is happening...'), 'with punctuation');
  assert(!isDialogue('MAIN MENU'), 'all-caps UI');
  assert(!isDialogue('Fullscreen'), 'short UI');
  assert(!isDialogue('Settings.Resolution'), 'Settings key');

  // Test 2: isUI
  console.log('\n2. isUI');
  assert(isUI('MAIN MENU'), 'all caps');
  assert(isUI('Fullscreen'), 'short capitalized');
  assert(isUI('Settings.Resolution'), 'Settings key');
  assert(!isUI('And now hold still I\'m not done yet.'), 'long sentence');

  // Test 3: classify
  console.log('\n3. classify');
  assert(classify('Hello world') === 'ui', 'short 2-word phrase → ui');
  assert(classify('MAIN MENU') === 'ui', 'all caps → ui');
  assert(classify('And now hold still I\'m not done yet. Let me help you.') === 'dialogue', 'long dialogue');
  assert(classify('Fullscreen') === 'ui', 'settings → ui');

  // Test 4: extractStrings — basic filtering
  // extractStrings expects { files: [{ name: 'f', strings: [{raw, offset}] }] }
  console.log('\n4. extractStrings');
  const testInput = {
    files: [{
      name: 'test',
      strings: [
        { offset: 10, raw: 'MAIN MENU TITLE' },
        { offset: 20, raw: 'And now hold still I\'m not done yet.' },
        { offset: 30, raw: 'Fullscreen Mode' },
        { offset: 40, raw: 'm_ExecutionOrder' },
        { offset: 50, raw: 'Settings.Resolution' },
      ],
    }],
  };

  const result = extractStrings(testInput);
  assert(result.dialogs.test !== undefined, 'has dialogs for test file');
  assert(result.ui.test !== undefined, 'has ui for test file');
  assert(result.dialogs.test.some(s => s.raw === 'And now hold still I\'m not done yet.'), 'correct dialogue in dialogs');
  assert(result.ui.test.some(s => s.raw === 'MAIN MENU TITLE'), 'MAIN MENU in ui');
  assert(result.ui.test.some(s => s.raw === 'Fullscreen Mode'), 'Fullscreen in ui');
  assert(!result.ui.test.some(s => s.raw.includes('ExecutionOrder')), 'ExecutionOrder not in ui');

  // Test 5: Empty input
  console.log('\n5. Empty input');
  const empty = extractStrings({ files: [] });
  assert(Object.keys(empty.dialogs).length === 0, 'no dialogs');
  assert(Object.keys(empty.ui).length === 0, 'no ui');
  assert(Object.keys(empty.noise).length === 0, 'no noise');

  // Test 6: Safety — malformed strings
  console.log('\n6. Malformed strings');
  const malformed = extractStrings({
    files: [{ name: 'test', strings: [{ raw: null }, { raw: undefined }, { raw: '' }] }],
  });
  const allKeys = Object.keys(malformed.dialogs).concat(Object.keys(malformed.ui), Object.keys(malformed.noise));
  assert(allKeys.length >= 0, 'safe with null/empty');

  // Test 7: Min length filtering via options
  console.log('\n7. Min length option');
  const shortInput = {
    files: [{
      name: 'f',
      strings: [
        { raw: 'AB' },
        { raw: 'ABCDEFGHIJ' },
      ],
    }],
  };
  const shortResult = extractStrings(shortInput, { minLength: 20 });
  assert(Object.keys(shortResult.dialogs).length === 0 && Object.keys(shortResult.ui).length === 0, 'filtered by minLength');

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
