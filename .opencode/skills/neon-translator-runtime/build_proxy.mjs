#!/usr/bin/env node
import { mkdirSync, existsSync, statSync, copyFileSync, unlinkSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = resolve(join(__dirname, '..', '..', '..'));

const MSVC_TOOLS = 'C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Tools/MSVC/14.50.35717';
const CL = join(MSVC_TOOLS, 'bin/Hostx64/x64/cl.exe');
const SDK = 'C:/Program Files (x86)/Windows Kits/10';
const SDK_VER = '10.0.26100.0';

const INCLUDES = [
  join(MSVC_TOOLS, 'include'),
  join(SDK, 'Include', SDK_VER, 'shared'),
  join(SDK, 'Include', SDK_VER, 'um'),
  join(SDK, 'Include', SDK_VER, 'ucrt'),
];

const LIBS = [
  join(MSVC_TOOLS, 'lib', 'x64'),
  join(SDK, 'Lib', SDK_VER, 'ucrt', 'x64'),
  join(SDK, 'Lib', SDK_VER, 'um', 'x64'),
];

const SOURCE = join(__dirname, 'source', 'dwmapi_proxy.c');
const OUT_PATH = join(GAME_DIR, 'dwmapi.dll');
const REAL_COPY = join(GAME_DIR, 'dwmapi_real.dll');

async function main() {
  console.log('dwmapi.dll — Build (Native Proxy)\n');

  // Step 1: Copy real System32\dwmapi.dll -> dwmapi_real.dll (forwarder target)
  const systemDwmapi = `${process.env.SystemRoot || 'C:\\Windows'}\\System32\\dwmapi.dll`;
  console.log(`  Real dwmapi: ${systemDwmapi}`);
  try {
    copyFileSync(systemDwmapi, REAL_COPY);
    console.log('  -> dwmapi_real.dll copied to game root');
  } catch (e) {
    console.error(`  FAILED to copy dwmapi_real.dll: ${e.message}`);
    process.exit(1);
  }

  // Step 2: Remove old proxy files if present
  for (const old of ['version.dll', 'version_proxy.c', 'winhttp.dll']) {
    const p = join(GAME_DIR, old);
    try { unlinkSync(p); console.log(`  Removed old: ${old}`); } catch (_) {}
  }

  // Step 3: Check source
  if (!existsSync(SOURCE)) {
    console.error('ERROR: missing source/dwmapi_proxy.c');
    process.exit(1);
  }
  if (!existsSync(CL)) {
    console.error('ERROR: cl.exe not found at ' + CL);
    process.exit(1);
  }
  console.log('  Compiler:', CL);

  // Step 4: Compile
  const args = [
    '/nologo',
    '/O1',
    '/MD',
    '/LD',
    '/UTF-8',
    `/Fe${OUT_PATH}`,
    ...INCLUDES.map(p => `/I${p}`),
    SOURCE,
    '/link',
    ...LIBS.map(p => `/LIBPATH:${p}`),
    '/MACHINE:X64',
    'kernel32.lib',
  ];

  console.log('  Compiling...\n');

  const result = spawnSync(CL, args, {
    stdio: 'pipe',
    timeout: 60000,
    encoding: 'utf8',
    cwd: GAME_DIR,
  });

  if (result.status === 0) {
    const size = statSync(OUT_PATH).size;
    console.log(`  OK: dwmapi.dll (${(size / 1024).toFixed(1)} KB)`);
    const realSize = statSync(REAL_COPY).size;
    console.log(`  OK: dwmapi_real.dll (${(realSize / 1024).toFixed(1)} KB) — forwarder target`);
    console.log('\n  Restart game to load the new proxy!');
  } else {
    console.error('BUILD FAILED:');
    console.error(result.stdout || result.stderr || 'Unknown error');
    process.exit(1);
  }
}

main().catch(console.error);
