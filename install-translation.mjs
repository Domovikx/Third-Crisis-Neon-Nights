#!/usr/bin/env node

import { createWriteStream } from 'node:fs';
import { createReadStream } from 'node:fs';
import { mkdir, rm, readFile, writeFile } from 'node:fs/promises';
import { pipeline } from 'node:stream/promises';
import { createGunzip } from 'node:zlib';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { spawn } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = __dirname;

const BEPINEX_URL = 'https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip';
const XUNITY_URL = 'https://github.com/bbepis/XUnity.AutoTranslator/releases/download/v5.6.1/XUnity.AutoTranslator-BepInEx-5.6.1.zip';

const TEMP_DIR = join(GAME_DIR, '.install_temp');

async function log(msg) {
    console.log(`[install] ${msg}`);
}

async function question(q) {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    return new Promise(resolve => {
        rl.question(q, answer => {
            rl.close();
            resolve(answer);
        });
    });
}

async function downloadFile(url, dest) {
    log(`Скачивание: ${url.split('/').pop()}`);
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const file = createWriteStream(dest);
    await pipeline(response.body, file);
    
    log(`Сохранено: ${dest}`);
}

async function extractZip(zipPath, destDir) {
    log(`Распаковка: ${zipPath.split(/[/\\]/).pop()}`);
    
    return new Promise((resolve, reject) => {
        const ps = spawn('powershell', [
            '-NoProfile',
            '-Command',
            `Expand-Archive -Path "${zipPath}" -DestinationPath "${destDir}" -Force`
        ], { shell: true });
        
        ps.on('close', code => {
            if (code === 0) resolve();
            else reject(new Error(`powershell exit code: ${code}`));
        });
        ps.on('error', reject);
    });
}

async function moveContents(from, to) {
    const fs = await import('node:fs');
    
    if (!fs.existsSync(to)) {
        fs.mkdirSync(to, { recursive: true });
    }
    
    const entries = fs.readdirSync(from, { withFileTypes: true });
    for (const entry of entries) {
        const src = join(from, entry.name);
        const dest = join(to, entry.name);
        
        if (entry.isDirectory()) {
            await moveContents(src, dest);
        } else {
            fs.renameSync(src, dest);
        }
    }
}

async function configureGoogleTranslateV2() {
    const configPath = join(GAME_DIR, 'BepInEx', 'config', 'AutoTranslatorConfig.ini');
    
    log('Настройка GoogleTranslateV2...');
    
    let content = '';
    try {
        content = await readFile(configPath, 'utf-8');
    } catch {
        log('Конфиг не найден, будет создан при первом запуске игры');
        return;
    }
    
    content = content.replace(/^Endpoint=.*$/m, 'Endpoint=GoogleTranslateV2');
    content = content.replace(/^Language=.*$/m, 'Language=ru');
    content = content.replace(/^FromLanguage=.*$/m, 'FromLanguage=en');
    
    await writeFile(configPath, content, 'utf-8');
    log('Конфиг обновлен');
}

async function main() {
    log('='.repeat(50));
    log('Установка перевода для Third Crisis Neon Nights');
    log('='.repeat(50));
    
    const needInstall = await question('\nПродолжить? (y/n): ');
    if (!needInstall.toLowerCase().startsWith('y')) {
        log('Отменено');
        process.exit(0);
    }
    
    try {
        await mkdir(TEMP_DIR, { recursive: true });
        
        const bepinexZip = join(TEMP_DIR, 'BepInEx.zip');
        const xunityZip = join(TEMP_DIR, 'XUnity.zip');
        
        await downloadFile(BEPINEX_URL, bepinexZip);
        await downloadFile(XUNITY_URL, xunityZip);
        
        const bepinexExtract = join(TEMP_DIR, 'BepInEx');
        await mkdir(bepinexExtract, { recursive: true });
        await extractZip(bepinexZip, bepinexExtract);
        
        const xunityExtract = join(TEMP_DIR, 'XUnity');
        await mkdir(xunityExtract, { recursive: true });
        await extractZip(xunityZip, xunityExtract);
        
        const bepinexInner = join(bepinexExtract, 'BepInEx');
        if (require('node:fs').existsSync(bepinexInner)) {
            await moveContents(bepinexInner, join(GAME_DIR, 'BepInEx'));
        } else {
            await moveContents(bepinexExtract, join(GAME_DIR, 'BepInEx'));
        }
        
        const xunityInner = join(xunityExtract, 'BepInEx');
        if (require('node:fs').existsSync(xunityInner)) {
            await moveContents(xunityInner, join(GAME_DIR, 'BepInEx'));
        } else {
            const contents = require('node:fs').readdirSync(xunityExtract);
            for (const item of contents) {
                const src = join(xunityExtract, item);
                const dest = join(GAME_DIR, item);
                await moveContents(src, dest);
            }
        }
        
        const extraFiles = ['doorstop_config.ini', '.doorstop_version'];
        for (const f of extraFiles) {
            const src = join(bepinexExtract, f);
            const dest = join(GAME_DIR, f);
            if (require('node:fs').existsSync(src)) {
                require('node:fs').renameSync(src, dest);
            }
        }
        
        await configureGoogleTranslateV2();
        
        log('Очистка временных файлов...');
        await rm(TEMP_DIR, { recursive: true, force: true });
        
        log('='.repeat(50));
        log('Установка завершена!');
        log('='.repeat(50));
        log('');
        log('Запустите игру для начала перевода.');
        log('Горячие клавиши:');
        log('  ALT+0 - UI переводчика');
        log('  ALT+T - вкл/выкл перевод');
        log('  ALT+R - перезагрузить перевод');
        log('  ALT+U - ручной перевод');
        
    } catch (err) {
        log(`Ошибка: ${err.message}`);
        console.error(err);
        process.exit(1);
    }
}

main();