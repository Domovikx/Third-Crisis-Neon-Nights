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
 * Extract aligned strings (int32 LE length + UTF-8 data) from buffer.
 *
 * Unity serializes string fields as:
 *   4 bytes: int32 LE length
 *   N bytes: UTF-8 string data
 *   padding to 4-byte boundary (null bytes)
 *
 * Uses text-run approach: scans for printable ASCII runs, then checks
 * if a valid length prefix exists 1-4 bytes before the text.
 *
 * Returns array of { offset, raw, length, type: 'aligned' } objects.
 */
export function extractAlignedStrings(buf, dataOffset, dataEnd) {
  const result = [];
  const seen = new Set();

  let i = dataOffset;
  while (i < dataEnd) {
    // Fast-forward to next printable ASCII character
    while (i < dataEnd && (buf[i] < 32 || buf[i] > 126)) i++;
    if (i >= dataEnd) break;

    const textStart = i;

    // Measure text run length
    let textLen = 0;
    while (i + textLen < dataEnd && buf[i + textLen] >= 32 && buf[i + textLen] <= 126) textLen++;
    i += textLen;

    // A valid aligned string text run is 3-200 chars
    if (textLen < 3 || textLen > 200) continue;

    // Try to find a length prefix in the 4 bytes before textStart
    for (let offset = -4; offset < 0; offset++) {
      const prefixPos = textStart + offset;
      if (prefixPos < dataOffset) continue;

      const storedLen = buf.readUInt32LE(prefixPos);
      if (storedLen < 3 || storedLen > 200) continue;
      if (prefixPos + 4 + storedLen > dataEnd) continue;

      // Read the string at the claimed position
      const candidate = buf.toString('utf-8', prefixPos + 4, prefixPos + 4 + storedLen);
      if (!candidate) continue;

      // Verify: our text run should start with this candidate
      const text = buf.toString('utf-8', textStart, textStart + Math.min(textLen, 60));
      if (!text.startsWith(candidate.substring(0, Math.min(candidate.length, text.length)))) continue;

      // Validate content: must be mostly clean ASCII text
      let letters = 0;
      let spaces = 0;
      for (let ci = 0; ci < candidate.length; ci++) {
        const cc = candidate.charCodeAt(ci);
        if ((cc >= 65 && cc <= 90) || (cc >= 97 && cc <= 122)) letters++;
        if (cc === 32) spaces++;
      }
      if (letters === 0 && spaces === 0) continue;
      if (letters + spaces < candidate.length * 0.4) continue;

      const clean = candidate.trim();
      if (clean.length < 3) continue;

      const key = `${prefixPos}:${clean}`;
      if (seen.has(key)) continue;
      seen.add(key);

      result.push({
        offset: prefixPos,
        raw: clean,
        length: storedLen,
        type: 'aligned',
      });

      break; // One match per text run
    }
  }

  return result;
}

// ====== Metadata parsing ======

/**
 * Parse the metadata section of a Unity serialized file (v22 format).
 *
 * Scans the metadata for the SerializedType array and ObjectInfo table.
 *
 * @param {Buffer} buf - File buffer
 * @param {number} [metadataOffset=60] - Byte offset where metadata begins
 * @param {number} [fileSize] - Total file size (for validation)
 * @returns {{ platform: number, typeCount: number, types: Array, objectCount: number, objects: Array }}
 */
export function parseUnityMetadata(buf, header = null, fileSize) {
  if (fileSize === undefined) fileSize = buf.length;

  const metadataOffset = 60;

  // Platform (int32 LE) — 19 = StandaloneWindows64
  const platform = buf.readInt32LE(metadataOffset);

  // --- Scan for SerializedType array ---
  let offset = metadataOffset + 4;
  let typeCount = 0;
  let types = [];

  while (offset <= buf.length - 12) {
    const candidate = buf.readInt32LE(offset);
    if (candidate > 0 && candidate <= 200) {
      const result = readTypeArray(buf, offset + 4, candidate);
      if (result) {
        typeCount = candidate;
        types = result.types;
        offset = result.nextOffset;
        break;
      }
    }
    offset += 4;
  }

  // --- Scan for ObjectInfo table ---
  let objectCount = 0;
  let objects = [];

  const scanStart = typeCount > 0 ? offset : metadataOffset + 4;
  offset = scanStart;

  while (offset <= buf.length - 28) {
    const candidate = buf.readInt32LE(offset);
    if (candidate >= 100 && candidate <= 10000) {
      const records = readObjectInfoTable(buf, offset + 4, candidate, fileSize);
      if (records) {
        objectCount = candidate;
        objects = records;
        break;
      }
    }
    offset += 4;
  }

  return { platform, typeCount, types, objectCount, objects };
}

/**
 * Attempt to read a SerializedType array at the given offset.
 * Each entry is 8 bytes when stripped; variable when typeTreeExists == 1.
 * Returns null if the data doesn't look like a valid type array.
 */
function readTypeArray(buf, startOffset, count) {
  const types = [];
  let offset = startOffset;

  for (let i = 0; i < count; i++) {
    if (offset + 8 > buf.length) return null;
    const classID = buf.readInt32LE(offset);
    if (classID < -1 || classID > 10000) return null;

    const isStripped = buf[offset + 4];
    const scriptTypeIndex = buf.readInt16LE(offset + 5);
    const typeTreeExists = buf[offset + 7];
    let entrySize = 8;

    if (typeTreeExists) {
      const skip = skipUnityTypeTree(buf, offset + 8);
      if (skip === null) return null;
      entrySize += skip;
    }

    types.push({
      classID,
      isStripped: isStripped !== 0,
      scriptTypeIndex,
      typeTreeExists: typeTreeExists !== 0,
    });

    offset += entrySize;
  }

  if (types.length !== count) return null;
  return { types, nextOffset: offset };
}

/**
 * Try to skip past a TypeTree blob (when typeTreeExists == 1).
 * Uses Unity 2022 TypeTree layout (28 bytes per node).
 * Returns number of bytes skipped, or null on failure.
 */
function skipUnityTypeTree(buf, offset) {
  let pos = offset;

  // 16-byte hash / script ID
  if (pos + 20 > buf.length) return null;
  pos += 16;

  // Node count (int32 LE)
  const nodeCount = buf.readInt32LE(pos);
  pos += 4;
  if (nodeCount < 0 || nodeCount > 10000) return null;

  // Each TypeTreeNode is 28 bytes in Unity 2022
  const NODE_SIZE = 28;
  const nodesByteLen = nodeCount * NODE_SIZE;
  if (pos + nodesByteLen + 4 > buf.length) return null;
  pos += nodesByteLen;

  // String buffer length (int32 LE)
  const strBufLen = buf.readInt32LE(pos);
  pos += 4;
  if (strBufLen < 0 || strBufLen > 5_000_000) return null;
  if (pos + strBufLen > buf.length) return null;
  pos += strBufLen;

  return pos - offset;
}

/**
 * Try to read an ObjectInfo table at the given offset.
 * Each record is 24 bytes (6 × int32 LE).
 * Returns array of { pathID, byteStart, byteEnd, typeID } or null if invalid.
 */
function readObjectInfoTable(buf, startOffset, count, fileSize) {
  if (count <= 0) return null;
  if (startOffset + count * 24 > buf.length) return null;

  // Validate first few records
  const maxCheck = Math.min(count, 5);
  for (let i = 0; i < maxCheck; i++) {
    const roff = startOffset + i * 24;
    const typeID = buf.readInt32LE(roff);
    const byteStart = buf.readInt32LE(roff + 4);
    if (typeID < 1 || typeID >= 500) return null;
    if (byteStart < 0 || byteStart >= fileSize) return null;
  }

  const objects = [];
  for (let i = 0; i < count; i++) {
    const roff = startOffset + i * 24;
    const typeID = buf.readInt32LE(roff);
    const byteStart = buf.readInt32LE(roff + 4);
    const byteEnd = buf.readInt32LE(roff + 8);
    const pathID_low = buf.readInt32LE(roff + 16);
    const pathID_high = buf.readInt32LE(roff + 20);

    let pathID;
    if (pathID_high === 0) {
      pathID = pathID_low >>> 0;
    } else {
      pathID = `${(pathID_high >>> 0).toString(16)}${(pathID_low >>> 0).toString(16).padStart(8, '0')}`;
    }

    objects.push({ pathID, byteStart, byteEnd, typeID });
  }

  return objects;
}

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

  const dataEnd = header.dataOffset + (header.fileSize - header.dataOffset);
  const nullTermStrings = extractUnityStrings(buf, header.dataOffset);
  const alignedStrings = extractAlignedStrings(buf, header.dataOffset, dataEnd);

  // Merge and sort by offset
  const allStrings = [...nullTermStrings, ...alignedStrings].sort((a, b) => a.offset - b.offset);

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
    strings: allStrings,
    stats: {
      totalStrings: allStrings.length,
      dataSize: header.fileSize - header.dataOffset,
      nullTerminated: nullTermStrings.length,
      aligned: alignedStrings.length,
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
  for (let i = 0; i <= 15; i++)
    files.push({ name: `sharedassets${i}`, path: join(DATA_DIR, `sharedassets${i}.assets`), type: 'unity' });
  files.push({ name: 'resources', path: join(DATA_DIR, 'resources.assets'), type: 'unity' });
  files.push({ name: 'globalgamemanagers', path: join(DATA_DIR, 'globalgamemanagers.assets'), type: 'unity' });
  files.push({ name: 'Assembly-CSharp', path: join(DATA_DIR, 'Managed', 'Assembly-CSharp.dll'), type: 'raw' });
  files.push({ name: 'Assembly-CSharp-firstpass', path: join(DATA_DIR, 'Managed', 'Assembly-CSharp-firstpass.dll'), type: 'raw' });
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
    parser: 'parse-unity v4',
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
