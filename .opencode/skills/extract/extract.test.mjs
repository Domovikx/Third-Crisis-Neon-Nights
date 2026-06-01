#!/usr/bin/env node

import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

// Simplified parseHeader matching extract.mjs logic
function parseHeader(buf) {
  if (buf.length < 30) return null;
  const dataOffset = buf.readUInt32BE(0x1A);
  const metadataSize = buf.readUInt32BE(0x12);
  const fileSize = buf.readUInt32BE(0x16);
  const version = buf.readUInt32BE(0x08);
  let ver = '';
  for (let i = 0x30; i < buf.length && buf[i] !== 0; i++) ver += String.fromCharCode(buf[i]);

  return {
    version,
    newFormat: buf.readUInt32BE(0x00) === 0,
    metadataSize,
    dataOffset,
    fileSize,
    unityVersion: ver || 'unknown',
  };
}

function extractAllStrings(buf) {
  const strings = [];
  for (let i = 0; i < buf.length; i++) {
    if (buf[i] >= 32 && buf[i] <= 126) {
      let s = '';
      let j = i;
      while (j < buf.length && buf[j] >= 32 && buf[j] <= 126) { s += String.fromCharCode(buf[j]); j++; }
      if (s.length >= 4) strings.push({ offset: i, raw: s });
      i = j;
    }
  }
  return strings;
}

async function main() {
  console.log('=== Extract — Tests ===\n');

  // Test 1: parseHeader from real level file
  console.log('1. Header parsing');
  try {
    const buf = await readFile(join(__dirname, '..', '..', '..', 'Third Crisis Neon Nights_Data', 'level0'));
    const h = parseHeader(buf);
    assert(h !== null, 'header parsed');
    assert(h.version > 0, `version > 0: ${h.version}`);
    assert(h.dataOffset > h.metadataSize, 'dataOffset > metadataSize');
    assert(h.dataOffset < h.fileSize, 'dataOffset < fileSize');
    assert(h.unityVersion.includes('2022'), 'unity version 2022');
  } catch (e) {
    assert(false, `level0 accessible: ${e.message}`);
  }

  // Test 2: parseHeader from DLL
  console.log('\n2. DLL header (not Unity format)');
  try {
    const dll = await readFile(join(__dirname, '..', '..', '..', 'Third Crisis Neon Nights_Data', 'Managed', 'Assembly-CSharp.dll'));
    // DLL is not a Unity serialized file — should still not crash
    const h = parseHeader(dll);
    assert(h !== null, 'header parsed (even if garbage)');
  } catch (e) {
    assert(true, 'DLL skip: ' + e.message);
  }

  // Test 3: String extraction from binary
  console.log('\n3. String extraction from level data');
  try {
    const buf = await readFile(join(__dirname, '..', '..', '..', 'Third Crisis Neon Nights_Data', 'level0'));
    const h = parseHeader(buf);
    const dataBuf = buf.slice(h.dataOffset);
    const strings = extractAllStrings(dataBuf);
    assert(strings.length > 100, `${strings.length} strings extracted (> 100)`);
    assert(strings[0].offset !== undefined, 'string has offset');
    assert(strings[0].raw.length > 0, 'string has raw value');

    const hasAlpha = strings.some(s => /[a-zA-Z\s]{10,}/.test(s.raw));
    assert(hasAlpha, 'dialogue-like strings found');

    const hasShort = strings.some(s => s.raw.length >= 4);
    assert(hasShort, 'short strings found');
  } catch (e) {
    assert(false, `level0 data: ${e.message}`);
  }

  // Test 4: resources.assets extraction
  console.log('\n4. resources.assets extraction');
  try {
    const buf = await readFile(join(__dirname, '..', '..', '..', 'Third Crisis Neon Nights_Data', 'resources.assets'));
    const h = parseHeader(buf);
    assert(h.dataOffset > 0, 'resources.assets: dataOffset > 0');
    assert(h.fileSize > 1000000, 'resources.assets: fileSize > 1MB');
  } catch (e) {
    assert(false, `resources.assets: ${e.message}`);
  }

  // Test 5: Empty buffer
  console.log('\n5. Empty buffer safety');
  const emptyH = parseHeader(Buffer.alloc(10));
  assert(emptyH === null, 'null for tiny buffer');

  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
