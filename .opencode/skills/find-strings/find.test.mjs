#!/usr/bin/env node

import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
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

// Copy of extract() from find.mjs (no imports from main script)
function extract(buffer, minLen = 20) {
  const strings = [];
  let cur = '';
  for (let i = 0; i < buffer.length; i++) {
    const b = buffer[i];
    if (b >= 32 && b <= 126) { cur += String.fromCharCode(b); }
    else {
      if (cur.length >= minLen) {
        const alpha = (cur.match(/[a-zA-Z]/g) || []).length / cur.length;
        if (alpha > 0.5 && !/^[0-9a-fA-F\s]+$/.test(cur)) strings.push(cur);
      }
      cur = '';
    }
  }
  return [...new Set(strings)];
}

async function main() {
  console.log('=== find-strings — Tests ===\n');

  await mkdir(TEST_DIR, { recursive: true });

  // Test 1: Extract English strings from binary
  console.log('1. Basic extraction');

  // Build a binary buffer simulating a game file
  const buf = Buffer.concat([
    Buffer.from([0x00, 0x01, 0x02]), // noise
    Buffer.from('MAIN MENU', 'ascii'),
    Buffer.from([0x00]), // null terminator
    Buffer.from([0xFF, 0xFE]), // noise
    Buffer.from('Resolution Scaling', 'ascii'),
    Buffer.from([0x00]),
    Buffer.from('abcdef1234', 'ascii'), // garbage (all hex)
    Buffer.from([0x00]),
    Buffer.from('Fullscreen Mode', 'ascii'),
    Buffer.from([0x00]),
  ]);

  const strings = extract(buf, 5);
  assert(strings.includes('MAIN MENU'), 'MAIN MENU found');
  assert(strings.includes('Resolution Scaling'), 'Resolution Scaling found');
  assert(strings.includes('Fullscreen Mode'), 'Fullscreen Mode found');
  assert(!strings.includes('abcdef1234'), 'hex garbage excluded');

  // Test 2: Minimum length filtering
  console.log('\n2. Min length filtering');
  const buf2 = Buffer.concat([
    Buffer.from('AB', 'ascii'), Buffer.from([0x00]),
    Buffer.from('ABCDEFGH', 'ascii'), Buffer.from([0x00]),
  ]);
  const short = extract(buf2, 10);
  assert(short.length === 0, 'no strings shorter than 10 chars');

  const medium = extract(buf2, 4);
  assert(medium.includes('ABCDEFGH'), '8-char string found with minLen 4');

  // Test 3: Deduplication
  console.log('\n3. Deduplication');
  const buf3 = Buffer.concat([
    Buffer.from('Hello World', 'ascii'), Buffer.from([0x00]),
    Buffer.from('Hello World', 'ascii'), Buffer.from([0x00]),
    Buffer.from('Hello World', 'ascii'), Buffer.from([0x00]),
  ]);
  const dedup = extract(buf3, 5);
  assert(dedup.length === 1, 'deduped to 1');

  // Test 4: Alpha ratio filtering
  console.log('\n4. Alpha ratio filtering');
  const buf4 = Buffer.concat([
    Buffer.from('1111 2222 3333 4444', 'ascii'), Buffer.from([0x00]),
  ]);
  const numeric = extract(buf4, 5);
  assert(!numeric.includes('1111 2222 3333 4444'), 'numeric-only excluded');

  // Test 5: Empty buffer
  console.log('\n5. Empty buffer');
  const empty = extract(Buffer.alloc(0));
  assert(empty.length === 0, 'no strings from empty');

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
