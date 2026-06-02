#!/usr/bin/env node
/**
 * bundle-parser.mjs — Extract readable strings from Unity AssetBundles (.bundle)
 *
 * UnityFS v8 + LZ4HC decompression (pure JS LZ4 block decoder).
 * No Python, no external deps.
 * Outputs NDJSON in parser-compatible format.
 */

import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { isTranslationCandidate } from './parser.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const BUNDLE_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data', 'StreamingAssets', 'aa', 'StandaloneWindows64');

// ====== Pure LZ4 block decoder ======

function lz4BlockDecode(src, uncompressedSize) {
  const dst = Buffer.alloc(uncompressedSize);
  let sp = 0, dp = 0;

  while (sp < src.length && dp < uncompressedSize) {
    const token = src[sp++];
    let litLen = token >>> 4;
    let matchLen = (token & 0x0F) + 4;

    if (litLen === 15) {
      let add;
      do { add = src[sp++]; litLen += add; } while (add === 255);
    }

    for (let i = 0; i < litLen && sp < src.length && dp < uncompressedSize; i++) {
      dst[dp++] = src[sp++];
    }

    if (sp >= src.length || dp >= uncompressedSize) break;

    const matchOffset = src[sp++] | (src[sp++] << 8);
    if (matchOffset === 0) break;

    if (matchLen === 19) {
      let add;
      do { add = src[sp++]; matchLen += add; } while (add === 255);
    }

    const matchPos = dp - matchOffset;
    for (let i = 0; i < matchLen && dp < uncompressedSize; i++) {
      dst[dp++] = dst[matchPos + i];
    }
  }

  return dst.subarray(0, dp);
}

// ====== UnityFS header ======

function parseUnityFSHeader(buf) {
  if (buf.subarray(0, 7).toString('ascii') !== 'UnityFS') return null;

  const compressedHeaderSize = buf.readUInt32BE(38);
  const decompressedHeaderSize = buf.readUInt32BE(42);
  const flags = buf.readUInt32BE(46);
  const compressionType = flags & 0x3F;

  return {
    compressedHeaderSize,
    decompressedHeaderSize,
    compressionType,
    headerStart: 64,
    dataStart: 64 + compressedHeaderSize,
  };
}

// ====== String extraction ======

function extractRawStrings(buf, minLen = 4) {
  const result = [];
  let i = 0;
  while (i < buf.length) {
    if (buf[i] >= 32 && buf[i] < 127) {
      let j = i + 1;
      while (j < buf.length && buf[j] >= 32 && buf[j] < 127) j++;
      const s = buf.subarray(i, j).toString('ascii');
      if (s.length >= minLen && /[a-zA-Z]{3,}/.test(s)) {
        result.push({ offset: i, text: s });
      }
      i = j;
    } else {
      i++;
    }
  }
  return result;
}

// ====== Main ======

async function main() {
  const outDir = join(GAME_DIR, 'output', 'parser');
  await mkdir(outDir, { recursive: true });

  // Only process bundles likely to contain UI text
  const targetPatterns = ['level-', '3dsuitcasescene', 'releasenotesui'];
  const allBundles = (await readdir(BUNDLE_DIR))
    .filter(f => f.endsWith('.bundle') && targetPatterns.some(p => f.includes(p)));

  let totalStrings = 0;
  const manifest = [];

  for (const fname of allBundles) {
    const filePath = join(BUNDLE_DIR, fname);
    const buf = await readFile(filePath);

    const hdr = parseUnityFSHeader(buf);
    if (!hdr || hdr.compressionType !== 3) continue;

    // Decompress LZ4 header
    const compHeader = buf.subarray(hdr.headerStart, hdr.headerStart + hdr.compressedHeaderSize);
    let decompHeader;
    try {
      decompHeader = lz4BlockDecode(compHeader, hdr.decompressedHeaderSize);
    } catch {
      console.error(`  LZ4 failed for ${fname}`);
      continue;
    }

    const dataArea = buf.subarray(hdr.dataStart);

    // Extract strings and filter noise
    const allStrings = extractRawStrings(dataArea);
    const strings = allStrings.filter(s => isTranslationCandidate(s.text));
    // Parser output format: [offset, "raw"]
    const outData = strings.map(s => JSON.stringify([String(s.offset), s.text]));

    if (outData.length > 0) {
      const outName = `bundle-${fname.replace(/\.bundle$/, '').replace(/[^a-z0-9_-]/gi, '_')}.ndjson`;
      await writeFile(join(outDir, outName), outData.join('\n') + '\n');
      manifest.push({ file: fname, output: outName, totalStrings: outData.length });
      totalStrings += outData.length;
      console.log(`${fname.slice(0, 55)}: ${outData.length} raw strings`);
    }
  }

  await writeFile(join(outDir, 'bundle-manifest.json'),
    JSON.stringify({ totalBundles: manifest.length, totalStrings, bundles: manifest }, null, 2));
  console.log(`\nDone: ${totalStrings} strings from ${manifest.length} bundles`);
}

main().catch(console.error);
