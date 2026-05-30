#!/usr/bin/env node

import { readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseHeader, extractUnityStrings, extractRawStrings, parseUnityFile, parseRawFile } from './parser.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..', '..');
const DATA_DIR = join(ROOT, 'Third Crisis Neon Nights_Data');
const OUT_DIR = join(ROOT, 'output', 'parser');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

async function main() {
  console.log('=== parse-unity (parser only) tests ===\n');

  // Test 1: Header parsing
  console.log('1. Header parsing');
  const buf3 = await readFile(join(DATA_DIR, 'level3'));
  const h3 = parseHeader(buf3);

  assert(h3.version === 22, 'version = 22');
  assert(h3.newFormat === true, 'new format detected');
  assert(h3.metadataSize > 500000 && h3.metadataSize < 2000000, `metadataSize plausible: ${h3.metadataSize}`);
  assert(h3.dataOffset > h3.metadataSize, `dataOffset > metadataSize: ${h3.dataOffset} > ${h3.metadataSize}`);
  assert(h3.dataOffset < h3.fileSize, `dataOffset < fileSize: ${h3.dataOffset} < ${h3.fileSize}`);
  assert(h3.fileSize > 5000000, `fileSize > 5MB: ${h3.fileSize}`);
  assert(h3.unityVersion === '2022.3.62f3', `unity version: ${h3.unityVersion}`);

  // Test 2: Multiple level files
  console.log('\n2. Level file consistency');
  for (const f of ['level0', 'level3', 'level7', 'level11', 'level15']) {
    const buf = await readFile(join(DATA_DIR, f));
    const h = parseHeader(buf);
    assert(h.version === 22, `${f}: version 22`);
    assert(h.dataOffset > 0 && h.dataOffset < buf.length, `${f}: valid dataOffset ${h.dataOffset}`);
    assert(h.metadataSize > 0 && h.metadataSize < buf.length, `${f}: valid metadataSize ${h.metadataSize}`);
    assert(h.newFormat, `${f}: newFormat`);
  }

  // Test 3: String extraction from data section
  console.log('\n3. String extraction');
  const strings = extractUnityStrings(buf3, h3.dataOffset);
  assert(strings.length > 1000, `level3: ${strings.length} strings found (> 1000)`);

  const hasDialogue = strings.some(s =>
    /[Ii]\'m|you\'re|don\'t|can\'t|he\'s|she\'s/i.test(s.raw)
  );
  assert(hasDialogue, 'found strings with contractions');

  // Each string has offset, raw, length
  assert(strings[0].offset !== undefined, 'string has offset');
  assert(strings[0].raw !== undefined, 'string has raw value');
  assert(strings[0].length !== undefined, 'string has length');
  assert(strings[0].contextHex !== undefined, 'string has contextHex');

  // Test 4: DLL raw string extraction
  console.log('\n4. DLL extraction');
  try {
    const dllBuf = await readFile(join(DATA_DIR, 'Managed', 'Assembly-CSharp.dll'));
    const dllStrings = extractRawStrings(dllBuf);
    assert(dllStrings.length > 100, `DLL: ${dllStrings.length} strings found (> 100)`);
    assert(dllStrings[0].offset !== undefined, 'DLL string has offset');
    assert(dllStrings[0].raw.length > 0, 'DLL string has non-empty raw');
  } catch (e) {
    assert(false, `DLL accessible: ${e.message}`);
  }

  // Test 5: parseUnityFile returns structured result
  console.log('\n5. parseUnityFile()');
  const result = await parseUnityFile(join(DATA_DIR, 'level0'), 'level0');
  assert(result.name === 'level0', 'result name');
  assert(result.type === 'unity', 'result type unity');
  assert(result.header.version === 22, 'result header version');
  assert(result.strings.length > 0, 'result has strings');
  assert(result.stats.totalStrings === result.strings.length, 'stats match');

  // Test 6: Parser generates correct NDJSON output
  console.log('\n6. NDJSON output');
  try {
    // Check manifest
    const manifestStr = await readFile(join(OUT_DIR, 'manifest.json'), 'utf-8');
    const manifest = JSON.parse(manifestStr);
    assert(manifest.parser === 'parse-unity v3', 'parser version in manifest');
    assert(manifest.totalStrings > 0, 'totalStrings > 0');
    assert(manifest.files.length > 0, 'files array non-empty');
    assert(manifest.files.some(f => f.type === 'unity'), 'has unity files');

    // Check at least one NDJSON file exists and has valid format
    const ndjsonStr = await readFile(join(OUT_DIR, 'level3.ndjson'), 'utf-8');
    const lines = ndjsonStr.trim().split('\n');
    assert(lines.length > 1000, `level3.ndjson: ${lines.length} lines`);
    const [offset, raw] = JSON.parse(lines[0]);
    assert(typeof offset === 'number', 'NDJSON line: offset is number');
    assert(typeof raw === 'string', 'NDJSON line: raw is string');
  } catch (e) {
    assert(false, `output: ${e.message}`);
  }

  // Test 7: sharedassets0
  console.log('\n7. sharedassets0 parsing');
  const saBuf = await readFile(join(DATA_DIR, 'sharedassets0.assets'));
  const saH = parseHeader(saBuf);
  assert(saH.version === 22, `sharedassets0: version ${saH.version}`);
  assert(saH.metadataSize > 0, `sharedassets0: metadataSize ${saH.metadataSize}`);
  assert(saH.dataOffset > 0, `sharedassets0: dataOffset ${saH.dataOffset}`);

  const saStrings = extractUnityStrings(saBuf, saH.dataOffset);
  assert(saStrings.length > 500, `sharedassets0: ${saStrings.length} strings`);

  // ====== Summary ======
  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
