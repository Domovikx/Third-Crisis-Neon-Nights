#!/usr/bin/env node

/**
 * Парсер Unity serialized file format (чистый Node.js, без библиотек).
 * Извлекает строки для перевода из level файлов и sharedassets.
 *
 * Формат: https://docs.unity3d.com/Manual/FormatDescription.html
 * 
 * Unity serialized file:
 *   [Header] [Metadata] [Data]
 *   
 * Metadata содержит:
 *   - TypeTree (описание структуры всех типов)
 *   - Hierarchy (список объектов с типами и смещениями)
 *   - StringPool (все строковые константы)
 */

import { readFile, open, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');
const DATA_DIR = join(GAME_DIR, 'Third Crisis Neon Nights_Data');

class BufferReader {
    constructor(buf, bigEndian = false) {
        this.buf = buf;
        this.off = 0;
        this.big = bigEndian;
    }
    u8() { return this.buf[this.off++]; }
    i16() { this.off += 2; return this.big ? (this.buf[this.off - 2] << 8 | this.buf[this.off - 1]) : (this.buf[this.off - 2] | this.buf[this.off - 1] << 8); }
    i32() { this.off += 4; return this.big ? (this.buf[this.off - 4] << 24 | this.buf[this.off - 3] << 16 | this.buf[this.off - 2] << 8 | this.buf[this.off - 1]) : (this.buf[this.off - 4] | this.buf[this.off - 3] << 8 | this.buf[this.off - 2] << 16 | this.buf[this.off - 1] << 24); }
    u32() { return this.i32() >>> 0; }
    u64() {
        const lo = this.u32();
        const hi = this.u32();
        return BigInt(hi) * 0x100000000n + BigInt(lo);
    }
    i64() {
        const val = this.u64();
        return val >= 0x8000000000000000n ? -((~val + 1n) & 0xFFFFFFFFFFFFFFFFn) : val;
    }
    f32() {
        const arr = new Uint8Array(this.buf.slice(this.off, this.off + 4));
        this.off += 4;
        return new Float32Array(arr.buffer)[0];
    }
    str(len) {
        const s = this.buf.toString('utf-8', this.off, this.off + len);
        this.off += len;
        return s;
    }
    cstr() {
        const start = this.off;
        while (this.off < this.buf.length && this.buf[this.off] !== 0) this.off++;
        const s = this.buf.toString('utf-8', start, this.off);
        this.off++; // skip null
        return s;
    }
    align(n) { this.off = (this.off + n - 1) & ~(n - 1); }
    align4() { this.align(4); }
    skip(n) { this.off += n; }
    tell() { return this.off; }
    seek(o) { this.off = o; }
    size() { return this.buf.length; }
    eof() { return this.off >= this.buf.length; }
    remaining() { return this.size() - this.tell(); }
}

// ============== Unity Serialized File Header ==============
function parseHeader(buf) {
    const r = new BufferReader(buf);
    const metadataSize = r.u32();
    const fileSize = r.u32();
    const version = r.u32();
    const dataOffset = r.u32();
    const endianess = r.u8(); // 0 = little, 1 = big
    r.skip(3);

    const bigEndian = endianess === 1;

    return { metadataSize, fileSize, version, dataOffset, bigEndian, metadataOffset: r.tell() };
}

// ============== Aligned String Reader ==============
function readAlignedString(r) {
    const len = r.i32();
    if (len <= 0) return '';
    const str = r.str(len);
    // align to 4 bytes
    r.align4();
    return str;
}

// ============== Type Tree Node ==============
function readTypeTreeNode(r, version) {
    const type = r.i16();
    const numFields = r.i16();
    const byteSize = r.u32();
    const index = r.i32();
    const metaFlag = r.u32();
    const name = readAlignedString(r);
    const typeName = readAlignedString(r);
    return { type, numFields, byteSize, index, metaFlag, name, typeName, children: [] };
}

function readTypeTree(r, version) {
    const numNodes = r.i32();
    const nodes = [];
    const stringBufferSize = r.i32();
    const stringBuffer = r.buf.slice(r.tell(), r.tell() + stringBufferSize);
    r.skip(stringBufferSize);

    // Actually read nodes
    // For simplicity, we re-read from the saved position
    // The nodes are stored before the string buffer

    // Reset: we need to read nodes properly
    // But we already consumed the header, let me re-construct

    return nodes;
}

// ============== Simple String Extraction from Unity serialized ==============
// Instead of fully parsing the type tree (complex), we use a hybrid approach:
// 1. Parse header + metadata for object table 
// 2. For each object, try to extract strings based on known patterns

function extractStringBlock(buf, off, maxLen = 10000) {
    const r = new BufferReader(buf.slice(off, off + maxLen));
    const strings = [];

    // Try to parse as length-prefixed string (Unity format)
    while (r.remaining() > 5) {
        const len = r.i32();
        if (len > 0 && len < 10000 && len <= r.remaining()) {
            // Check if it looks like valid text
            const start = r.tell();
            let valid = true;
            let printable = 0;
            for (let i = 0; i < len && i < 200; i++) {
                const b = buf[start + i];
                if (b >= 32 && b <= 126) printable++;
                else if (b !== 13 && b !== 10 && b !== 9) { valid = false; break; }
            }
            if (valid && printable > len * 0.7) {
                const str = r.str(len);
                r.align4();
                if (str.length > 5) strings.push(str);
                continue;
            }
        }
        break;
    }
    return strings;
}

// ============== Extended ASCII extraction with length-prefixed support ==============
function extractAllStrings(buf) {
    const found = new Set();

    // Method 1: Null-terminated ASCII (existing)
    let cur = '';
    for (let i = 0; i < buf.length; i++) {
        const b = buf[i];
        if (b >= 32 && b <= 126) cur += String.fromCharCode(b);
        else {
            if (cur.length >= 12 && cur.length <= 500) {
                const letters = (cur.match(/[a-zA-Z]/g) || []).length;
                const ratio = letters / cur.length;
                const spaces = (cur.match(/\s/g) || []).length;
                const upper = (cur.match(/[A-Z]/g) || []).length;
                if (ratio > 0.35 && spaces < cur.length * 0.6) {
                    found.add(cur.trim());
                }
            }
            cur = '';
        }
    }

    return [...found].sort();
}

// ============== Smart extraction from Unity data regions ==============
function extractUnityStrings(buf) {
    const all = extractAllStrings(buf);
    
    // Filter out noise
    const noise = [
        /^[\s!-\/:-@\[-`{-~]+$/, /^[a-z_][a-z_0-9]*$/, /^[A-Z_][A-Z_0-9]*$/,
        /^\d+[xX]\d+/, /^\d+[x\/]/, /^v ?\d+\.\d+/, /^Unity/, /^System\./,
        /\.(prefab|unity|asset|mat|png|cs)$/i, /^Assets\//, /\//,
        /^Hidden\//, /^Mobile\//, /^Universal Render Pipeline/i,
        /^Blur Toolkit/i, /^Soft Mask/i, /^Library\//, /^Packages\//,
        /^[0-9a-fA-F]{16,}$/, /^[\+\/a-zA-Z0-9]{30,}={0,2}$/,
        /PATHFINDING/i, /^Shader/i,
        /^\[HideInInspector\]/i, /^Torchlight/i,
    ];

    const isNoise = s => noise.some(p => p.test(s));

    const dialogue = all.filter(s => {
        if (s.length < 12 || isNoise(s)) return false;
        const letters = (s.match(/[a-zA-Z]/g) || []).length;
        const spaces = (s.match(/\s/g) || []).length;
        const upper = (s.match(/[A-Z]/g) || []).length;
        // Dialogue: has spaces, has lowercase, some uppercase
        return spaces > 0 && letters > s.length * 0.4 && upper < letters * 0.9;
    });

    const ui = all.filter(s => {
        if (s.length < 3 || isNoise(s)) return false;
        const letters = (s.match(/[a-zA-Z]/g) || []).length;
        const upper = (s.match(/[A-Z]/g) || []).length;
        // UI: all caps, short
        if (s.length <= 40 && letters > 2 && upper === letters) {
            if (/^[A-Z0-9\s\-\.\,\!\?\:]{3,}$/.test(s.trim())) return true;
        }
        return false;
    });

    const other = all.filter(s => {
        if (s.length < 3 || isNoise(s)) return false;
        return !dialogue.includes(s) && !ui.includes(s);
    });

    return { dialogue: [...new Set(dialogue)], ui: [...new Set(ui)], other: [...new Set(other)] };
}

// ============== Main ==============
async function main() {
    console.log('=== Unity Serialized File Parser (Node.js) ===\n');

    const files = [
        ...Array.from({ length: 16 }, (_, i) => ({ name: `level${i}`, path: join(DATA_DIR, `level${i}`) })),
        { name: 'sharedassets0', path: join(DATA_DIR, 'sharedassets0.assets') },
    ];

    let allDialogue = [];
    let allUI = [];

    for (const { name, path: fp } of files) {
        try {
            const buf = await readFile(fp);
            const header = parseHeader(buf);

            // Extract strings from the whole file
            const extracted = extractUnityStrings(buf);

            // Also try to find the object table and extract from data regions
            // For now, just use the binary search on the whole file

            if (extracted.dialogue.length || extracted.ui.length) {
                console.log(`${name}: header version=${header.version}, dataOffset=0x${header.dataOffset.toString(16)}`);
                console.log(`  Диалогов: ${extracted.dialogue.length}, UI: ${extracted.ui.length}, Прочих: ${extracted.other.length}`);

                // Extract from data section only (after dataOffset) for better quality
                const dataOnly = extractUnityStrings(buf.slice(header.dataOffset));
                if (dataOnly.dialogue.length > extracted.dialogue.length * 0.5) {
                    // Use data section extraction if it's good
                }

                allDialogue.push(...extracted.dialogue);
                allUI.push(...extracted.ui);
            }
        } catch (err) {
            console.log(`${name}: ERROR - ${err.message}`);
        }
    }

    const uniqueDialogue = [...new Set(allDialogue)].sort();
    const uniqueUI = [...new Set(allUI)].sort();

    console.log(`\n=== ИТОГ ===`);
    console.log(`Диалоговых строк: ${uniqueDialogue.length}`);
    console.log(`UI-строк: ${uniqueUI.length}`);

    const outDir = __dirname;
    await writeFile(join(outDir, 'extracted-all.txt'), [...new Set([...uniqueDialogue, ...uniqueUI])].sort().join('\n'), 'utf-8');
    await writeFile(join(outDir, 'extracted-dialogue.txt'), uniqueDialogue.join('\n'), 'utf-8');
    await writeFile(join(outDir, 'extracted-ui.txt'), uniqueUI.join('\n'), 'utf-8');

    console.log(`\nСохранено в ${outDir}/`);

    // Show samples
    console.log(`\n=== Примеры диалогов (20) ===`);
    for (const s of uniqueDialogue.filter(s => s.length > 20).slice(0, 20)) console.log(`  ${s}`);

    console.log(`\n=== Примеры UI (15) ===`);
    for (const s of uniqueUI.slice(0, 15)) console.log(`  ${s}`);
}

main().catch(console.error);
