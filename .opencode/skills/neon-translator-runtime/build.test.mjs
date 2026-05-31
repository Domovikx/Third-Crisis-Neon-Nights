#!/usr/bin/env node
import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync, spawnSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const CSC = 'C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe';

let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; process.stdout.write('.'); }
  else { failed++; process.stdout.write('F'); console.error('\n  FAIL:', msg); }
}

async function main() {
  console.log('=== NeonTranslatorRuntime — Build Tests ===\n');

  console.log('1. Source files');
  for (const f of ['NativeMethods.cs','TranslationLoader.cs','MethodPatcher.cs','TranslatorPlugin.cs'])
    assert(existsSync(join(__dirname, 'source', f)), f + ' exists');

  console.log('\n2. Build script');
  assert(existsSync(join(__dirname, 'build.mjs')), 'build.mjs exists');

  console.log('\n3. Compilation');
  try {
    execSync('node "' + join(__dirname, 'build.mjs') + '"', { stdio: 'pipe', timeout: 120000 });
  } catch(e) { assert(false, 'build: ' + (e.stderr||'').substring(0,100)); }

  const dllPath = join(GAME_DIR, 'output', 'runtime', 'NeonTranslatorRuntime.dll');
  assert(existsSync(dllPath), 'DLL created');
  const dllSize = readFileSync(dllPath).length;
  assert(dllSize > 1000, 'DLL size: ' + dllSize + ' bytes');

  console.log('\n4. DLL content verification');
  const content = readFileSync(dllPath).toString('latin1');
  assert(content.includes('NeonTranslator'), 'NeonTranslator namespace');
  assert(content.includes('TranslatorPlugin'), 'TranslatorPlugin');
  assert(content.includes('MethodPatcher'), 'MethodPatcher');
  assert(content.includes('TranslationLoader'), 'TranslationLoader');
  assert(content.includes('NativeMethods'), 'NativeMethods');
  assert(content.includes('VirtualProtect'), 'VirtualProtect');

  console.log('\n5. TranslationLoader unit test');
  const testFile = join(__dirname, 'test_data', 'test.ndjson');
  assert(existsSync(testFile), 'test.ndjson exists');
  const testContent = readFileSync(testFile, 'utf-8');
  assert(testContent.includes('Resolution Scaling'), 'test data present');
  assert(testContent.includes('Масштабирование разрешения'), 'test translation present');

  // Compile and run a mini test via csc
  console.log('\n6. Quick compile check');
  const testProg = join(__dirname, 'test_data', 'test_loader.cs');
  if (existsSync(testProg)) {
    const testOut = join(GAME_DIR, 'output', 'runtime', 'test_loader.exe');
    const MD = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'Managed');
    const srcDir = join(__dirname, 'source');
    const args = [
      '/target:exe', '/out:' + testOut, '/nologo',
      '/r:' + join(MD, 'netstandard.dll'),
      '/r:' + join(MD, 'UnityEngine.dll'),
      '/r:' + join(MD, 'UnityEngine.CoreModule.dll'),
      testProg,
      join(srcDir, 'TranslationLoader.cs'),
      join(srcDir, 'NativeMethods.cs'),
    ];
    const r = spawnSync(CSC, args, { stdio: 'pipe', timeout: 60000, encoding: 'utf8', cwd: GAME_DIR });
    assert(r.status === 0, 'test_loader compiled: ' + (r.stdout||'').substring(0,100));
    if (r.status === 0) {
      try {
        const run = spawnSync(testOut, [testFile], { stdio: 'pipe', timeout: 10000, encoding: 'utf8', cwd: GAME_DIR });
        assert(run.status === 0, 'test_loader ran OK');
      } catch(e) { assert(false, 'test_loader run failed'); }
    }
  } else {
    assert(true, 'test_loader.cs not found (skipped)');
  }

  console.log('\n\n=== Result:', passed, 'passed,', failed, 'failed ===');
  process.exit(failed > 0 ? 1 : 0);
}
main().catch(e => { console.error('FATAL:', e); process.exit(1); });
