#!/usr/bin/env node
/**
 * parser.mjs — Pure Unity serialized binary parser
 *
 * Reads Unity serialized files (level*, sharedassets*.assets) and raw binaries (DLL).
 * Outputs structured JSON with all found strings, their offsets, and context.
 * No filtering, no classification — just parsing.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');

// ====== Header parsing ======

export function parseHeader(buf) {
  const isNewFormat = buf[0] === 0 && buf[1] === 0 && buf[2] === 0 && buf[3] === 0
    && buf[4] === 0 && buf[5] === 0 && buf[6] === 0 && buf[7] === 0;

  if (!isNewFormat) {
    // Old format (pre-2020)
    const metadataSize = buf.readUInt32LE(0);
    const fileSize = buf.readUInt32LE(4);
    const version = buf.readUInt32LE(8);
    const dataOffset = buf.readUInt32LE(12);
    const endian = buf[16];
    return {
      version, dataOffset, metadataSize, fileSize,
      endianess: endian, bigEndian: endian === 1,
      headerSize: 20, metadataOffset: 20,
      unityVersion: 'pre-2020', newFormat: false,
    };
  }

  // New format (Unity 2020+): bytes 0-7 zeros, rest BE
  const version = buf.readInt32BE(8);
  const endian = buf[16];
  const metadataSize = buf.readInt32BE(20);
  const fileSize = buf.readInt32BE(28);
  const dataOffset = buf.readInt32BE(36);
  const metadataOffset = dataOffset - metadataSize;

  let verEnd = 48;
  while (buf[verEnd] !== 0) verEnd++;
  const unityVersion = buf.toString('utf-8', 48, verEnd);

  return {
    version, dataOffset, metadataSize, fileSize,
    endianess: endian, bigEndian: endian === 1,
    headerSize: metadataOffset, metadataOffset,
    unityVersion, newFormat: true,
  };
}

// ====== String extraction ======

/**
 * Extract null-terminated strings from Unity data section.
 * Returns array of { offset, raw, contextHex } objects.
 */
export function extractUnityStrings(buf, dataOffset) {
  const dataBuf = buf.slice(dataOffset);
  const result = [];
  let cur = '';
  let startOffset = 0;

  for (let i = 0; i < dataBuf.length; i++) {
    const b = dataBuf[i];
    if (b >= 32 && b <= 126) {
      if (cur.length === 0) startOffset = i;
      cur += String.fromCharCode(b);
    } else {
      if (cur.length >= 4 && cur.length <= 500) {
        const letters = (cur.match(/[a-zA-Z]/g) || []).length;
        if (letters >= cur.length * 0.4) {
          const absOffset = dataOffset + startOffset;
          const ctxStart = Math.max(0, startOffset - 16);
          const ctxEnd = Math.min(dataBuf.length, startOffset + cur.length + 16);
          const contextHex = dataBuf.slice(ctxStart, ctxEnd).toString('hex').toUpperCase();
          result.push({
            offset: absOffset,
            raw: cur.trim(),
            length: cur.length,
            contextHex,
          });
        }
      }
      cur = '';
    }
  }

  return result;
}

/**
 * Extract null-terminated strings from arbitrary binary (e.g. DLL).
 * Returns array of { offset, raw, length } objects.
 */
export function extractRawStrings(buf) {
  const result = [];
  let cur = '';
  let startOffset = 0;

  for (let i = 0; i < buf.length; i++) {
    const b = buf[i];
    if (b >= 32 && b <= 126) {
      if (cur.length === 0) startOffset = i;
      cur += String.fromCharCode(b);
    } else {
      if (cur.length >= 4 && cur.length <= 500) {
        const letters = (cur.match(/[a-zA-Z]/g) || []).length;
        if (letters >= cur.length * 0.4) {
          result.push({
            offset: startOffset,
            raw: cur.trim(),
            length: cur.length,
          });
        }
      }
      cur = '';
    }
  }

  return result;
}

// ====== File-level parsing ======

export async function parseUnityFile(filepath, name) {
  const buf = await readFile(filepath);
  const header = parseHeader(buf);
  const strings = extractUnityStrings(buf, header.dataOffset);

  return {
    name,
    path: filepath,
    type: 'unity',
    header: {
      version: header.version,
      fileSize: header.fileSize,
      dataOffset: header.dataOffset,
      metadataOffset: header.metadataOffset,
      metadataSize: header.metadataSize,
      unityVersion: header.unityVersion,
      endianess: header.endianess,
      newFormat: header.newFormat,
    },
    strings,
    stats: {
      totalStrings: strings.length,
      dataSize: header.fileSize - header.dataOffset,
    },
  };
}

export async function parseRawFile(filepath, name) {
  const buf = await readFile(filepath);
  const strings = extractRawStrings(buf);

  return {
    name,
    path: filepath,
    type: 'raw',
    fileSize: buf.length,
    strings,
    stats: {
      totalStrings: strings.length,
    },
  };
}

// ====== Default files ======

function getDefaultFiles() {
  const DATA_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data');
  const files = [];
  for (let i = 0; i <= 15; i++)
    files.push({ name: `level${i}`, path: join(DATA_DIR, `level${i}`), type: 'unity' });
  files.push({ name: 'sharedassets0', path: join(DATA_DIR, 'sharedassets0.assets'), type: 'unity' });
  files.push({ name: 'Assembly-CSharp', path: join(DATA_DIR, 'Managed', 'Assembly-CSharp.dll'), type: 'raw' });
  return files;
}

// ====== CLI ======

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`Usage: node parser.mjs [options]

Options:
  --level N         Parse single level (0-15)
  --file <path>     Parse specific file
  --name <name>     Name for the file (defaults to filename)
  --type <type>     File type: 'unity' (default) or 'raw'
  --out <dir>       Output directory (default: output/parser/)
  --min-len <N>     Minimum string length (default: 4)
  --no-defaults     Do not include default files when --level not set
  --help, -h        Show this help

Output:
  manifest.json   — metadata (headers, stats)
  *.ndjson        — per-file NDJSON: [offset,"raw"]
`);
    return;
  }

  const levelFlag = args.includes('--level') ? parseInt(args[args.indexOf('--level') + 1]) : null;
  const fileFlag = args.includes('--file') ? args[args.indexOf('--file') + 1] : null;
  const nameFlag = args.includes('--name') ? args[args.indexOf('--name') + 1] : null;
  const typeFlag = args.includes('--type') ? args[args.indexOf('--type') + 1] : 'unity';
  const minLen = parseInt(args.includes('--min-len') ? args[args.indexOf('--min-len') + 1] : '4', 10);
  const outDir = args.includes('--out')
    ? args[args.indexOf('--out') + 1]
    : join(GAME_DIR, 'output', 'parser');

  const noDefaults = args.includes('--no-defaults');

  // Determine file list
  const files = [];

  if (fileFlag) {
    files.push({
      name: nameFlag || fileFlag.split(/[\\/]/).pop().replace(/\.\w+$/, ''),
      path: fileFlag,
      type: typeFlag,
    });
  } else if (levelFlag !== null) {
    const DATA_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data');
    files.push({
      name: `level${levelFlag}`,
      path: join(DATA_DIR, `level${levelFlag}`),
      type: 'unity',
    });
  } else if (!noDefaults) {
    files.push(...getDefaultFiles());
  } else {
    console.error('No files specified. Use --level, --file, or omit --no-defaults.');
    process.exit(1);
  }

  console.error(`Parser: ${files.length} file(s) to scan, min length ${minLen}\n`);

  const results = [];

  for (const f of files) {
    try {
      let result;
      if (f.type === 'unity') {
        result = await parseUnityFile(f.path, f.name);
      } else {
        result = await parseRawFile(f.path, f.name);
      }

      if (minLen > 4) {
        result.strings = result.strings.filter(s => s.length >= minLen);
        result.stats.totalStrings = result.strings.length;
      }

      results.push(result);

      console.error(`${f.name}: ${result.stats.totalStrings} strings found` +
        (f.type === 'unity' ? ` (data: ${((result.stats.dataSize) / 1024 / 1024).toFixed(2)} MB)` : ''));
    } catch (err) {
      console.error(`${f.name}: ERROR - ${err.message}`);
    }
  }

  // Write output: manifest.json (headers + stats) + per-file NDJSON
  await mkdir(outDir, { recursive: true });

  const manifest = {
    parser: 'parse-unity v3',
    timestamp: new Date().toISOString(),
    minLength: minLen,
    totalFiles: results.length,
    totalStrings: results.reduce((s, r) => s + r.stats.totalStrings, 0),
    files: results.map(r => ({
      name: r.name,
      type: r.type,
      header: r.header || null,
      fileSize: r.fileSize || null,
      stats: r.stats,
    })),
  };

  // Write manifest
  await writeFile(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf-8');

  // Write per-file NDJSON: [offset,"raw"]
  let written = 0;
  for (const r of results) {
    const lines = r.strings.map(s => JSON.stringify([s.offset, s.raw]));
    await writeFile(join(outDir, `${r.name}.ndjson`), lines.join('\n') + '\n', 'utf-8');
    written += r.strings.length;
  }

  console.error(`\n${manifest.totalStrings} strings → ${results.length} NDJSON files`);
  console.error(`  manifest: ${join(outDir, 'manifest.json')}`);
  console.error(`  data:     ${join(outDir, '*.ndjson')}`);
}

// Run CLI only when executed directly, not when imported
const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] === __filename || process.argv[1]?.endsWith('parser.mjs')) {
  main().catch(console.error);
}
