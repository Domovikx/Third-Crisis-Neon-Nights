#!/usr/bin/env node

import { readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..', '..');
const DATA_DIR = join(ROOT, 'Third Crisis Neon Nights_Data');
const OUT_DIR = join(ROOT, 'output', 'raw');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error(`\n  FAIL: ${msg}`); }
}

async function main() {
  console.log('=== parse-unity tests ===\n');

  // Test 1: Header parsing
  console.log('1. Header parsing');
  const buf3 = await readFile(join(DATA_DIR, 'level3'));

  assert(buf3[0] === 0 && buf3[7] === 0, 'new format marker (8 zeros)');
  assert(buf3.readInt32BE(8) === 22, 'version = 22');

  const metaSize3 = buf3.readInt32BE(20);
  const dataOff3 = buf3.readInt32BE(36);
  const fileSize3 = buf3.readInt32BE(28);

  assert(metaSize3 > 500000 && metaSize3 < 2000000, `metadataSize plausible: ${metaSize3}`);
  assert(dataOff3 > metaSize3, `dataOffset > metadataSize: ${dataOff3} > ${metaSize3}`);
  assert(dataOff3 < fileSize3, `dataOffset < fileSize: ${dataOff3} < ${fileSize3}`);
  assert(fileSize3 > 5000000, `fileSize > 5MB: ${fileSize3}`);

  const verStr = buf3.toString('utf-8', 48, 60).replace(/\0/g, '');
  assert(verStr === '2022.3.62f3', `unity version: ${verStr}`);

  // Test 2: Multiple level files have valid headers
  console.log('\n2. Level file consistency');
  let checkedFiles = 0;
  for (const f of ['level0', 'level3', 'level7', 'level11', 'level15']) {
    const buf = await readFile(join(DATA_DIR, f));
    const dOff = buf.readInt32BE(36);
    const mSize = buf.readInt32BE(20);
    assert(dOff > 0 && dOff < buf.length, `${f}: valid dataOffset ${dOff}`);
    assert(mSize > 0 && mSize < buf.length, `${f}: valid metadataSize ${mSize}`);
    assert(buf.readInt32BE(8) === 22, `${f}: version 22`);
    checkedFiles++;
  }
  assert(checkedFiles === 5, `checked ${checkedFiles} files`);

  // Test 3: String extraction finds dialogue
  console.log('\n3. String extraction quality');
  const dataBuf3 = buf3.slice(dataOff3);

  // Scan null-terminated strings
  const strings = [];
  let cur = '';
  for (let i = 0; i < dataBuf3.length; i++) {
    const b = dataBuf3[i];
    if (b >= 32 && b <= 126) cur += String.fromCharCode(b);
    else {
      if (cur.length >= 12 && cur.length <= 500) {
        const letters = (cur.match(/[a-zA-Z]/g) || []).length;
        if (letters >= cur.length * 0.35) strings.push(cur.trim());
      }
      cur = '';
    }
  }

  assert(strings.length > 1000, `level3: ${strings.length} strings found (> 1000)`);

  // Check for real dialogue patterns
  const hasDialogueMarkers = strings.some(s =>
    /[Ii]\'m|you\'re|don\'t|can\'t|he\'s|she\'s/i.test(s)
  );
  assert(hasDialogueMarkers, 'found strings with contractions');

  // Test 4: Parsed output files exist
  console.log('\n4. Output files');
  const outFiles = ['parsed-all.txt', 'parsed-dialogue.txt', 'parsed-ui.txt'];
  for (const f of outFiles) {
    try {
      await access(join(OUT_DIR, f));
      assert(true, `${f} exists`);
    } catch {
      assert(false, `${f} missing`);
    }
  }

  // Test 5: sharedassets0
  console.log('\n5. sharedassets0 parsing');
  const saBuf = await readFile(join(DATA_DIR, 'sharedassets0.assets'));
  const saMetaSize = saBuf.readInt32BE(20);
  const saDataOff = saBuf.readInt32BE(36);
  assert(saMetaSize > 0, `sharedassets0: metadataSize ${saMetaSize}`);
  assert(saDataOff > 0, `sharedassets0: dataOffset ${saDataOff}`);

  // ====== Summary ======
  console.log(`\n\n=== Result: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
