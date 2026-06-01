#!/usr/bin/env node
import { readFileSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = resolve(join(__dirname, '..', '..', '..'));
const CSC = resolve('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe');
const SOURCE_DIR = join(__dirname, 'source');
const DATA_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'Managed');

const SOURCE_FILES = ['NativeMethods.cs', 'TranslationLoader.cs', 'MethodPatcher.cs', 'TranslatorPlugin.cs', 'NeonLateUpdate.cs'];
const REF_DLLS = ['UnityEngine.dll', 'UnityEngine.CoreModule.dll', 'UnityEngine.UI.dll', 'UnityEngine.UIModule.dll', 'Unity.TextMeshPro.dll', 'netstandard.dll'];

async function main() {
  console.log('NeonTranslatorRuntime — Build\n');

  for (const f of SOURCE_FILES) {
    if (!existsSync(join(SOURCE_DIR, f))) {
      console.error('ERROR: missing source/' + f);
      process.exit(1);
    }
  }
  console.log('  Source files: OK');

  const refs = REF_DLLS.map(r => join(DATA_DIR, r)).filter(existsSync);
  if (refs.length < 4) {
    console.error('ERROR: Missing Unity assemblies');
    process.exit(1);
  }
  console.log('  Unity refs:', refs.length, 'DLLs');

  const outDir = join(GAME_DIR, 'runtime');
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, 'NeonTranslatorRuntime.dll');

  const args = [
    '/target:library',
    '/out:' + outPath,
    '/platform:x64',
    '/unsafe',
    '/nologo',
  ];
  for (const r of refs) args.push('/r:' + r);
  for (const f of SOURCE_FILES) args.push(join(SOURCE_DIR, f));

  console.log('  Compiler:', CSC, '\n');

  const result = spawnSync(CSC, args, { stdio: 'pipe', timeout: 60000, encoding: 'utf8', cwd: GAME_DIR });

  if (result.status === 0) {
    const size = statSync(outPath).size;
    console.log('  OK:', join('runtime', 'NeonTranslatorRuntime.dll'), '(' + (size / 1024).toFixed(1) + ' KB)');
  } else {
    console.error('BUILD FAILED:');
    console.error(result.stdout || result.stderr || 'Unknown error');
    process.exit(1);
  }
}

main().catch(console.error);
