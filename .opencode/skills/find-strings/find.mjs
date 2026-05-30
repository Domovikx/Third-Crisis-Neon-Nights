#!/usr/bin/env node

import { readFile, readdir, writeFile } from 'node:fs/promises';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');

const args = process.argv.slice(2);
const TARGET_DIR = args.includes('--dir') ? args[args.indexOf('--dir') + 1] : join(GAME_DIR, 'Third Crisis Neon Nights_Data');
const MIN_LEN = parseInt(args.includes('--min') ? args[args.indexOf('--min') + 1] : '20', 10);
const SKIP_EXTS = new Set(['.dll', '.exe', '.png', '.jpg', '.jpeg', '.wav', '.mp3', '.ogg', '.mp4', '.avi', '.bundle']);

function extract(buffer) {
    const strings = [];
    let cur = '';
    for (let i = 0; i < buffer.length; i++) {
        const b = buffer[i];
        if (b >= 32 && b <= 126) { cur += String.fromCharCode(b); }
        else {
            if (cur.length >= MIN_LEN) {
                const alpha = (cur.match(/[a-zA-Z]/g) || []).length / cur.length;
                if (alpha > 0.5 && !/^[0-9a-fA-F\s]+$/.test(cur)) strings.push(cur);
            }
            cur = '';
        }
    }
    return [...new Set(strings)];
}

async function scanFile(p) {
    if (SKIP_EXTS.has(extname(p).toLowerCase())) return [];
    try {
        const buf = await readFile(p);
        const strs = extract(buf);
        if (strs.length) {
            console.log(`\n--- ${p} ---`);
            for (const s of strs.slice(0, 20)) console.log(`  ${s}`);
            if (strs.length > 20) console.log(`  ... +${strs.length - 20}`);
        }
        return strs;
    } catch { return []; }
}

async function scanDir(dir, depth = 0) {
    if (depth > 3) return [];
    let all = [];
    for (const e of await readdir(dir, { withFileTypes: true })) {
        const fp = join(dir, e.name);
        if (e.isDirectory()) {
            if (!e.name.startsWith('.') && !['cache', 'core', 'patchers'].includes(e.name))
                all.push(...await scanDir(fp, depth + 1));
        } else all.push(...await scanFile(fp));
    }
    return all;
}

const all = await scanDir(TARGET_DIR);
const out = join(__dirname, 'extracted.txt');
await writeFile(out, [...new Set(all)].sort().join('\n'), 'utf-8');
console.log(`\n=== Найдено: ${all.length}, сохранено в ${out} ===`);
