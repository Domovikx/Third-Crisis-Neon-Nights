#!/usr/bin/env node
/**
 * extractor.mjs — Classifies and filters parsed strings
 *
 * Takes JSON from parser, applies heuristics to separate
 * dialogue from UI strings from noise (FSM state names, object names, etc.)
 *
 * Uses NOISE_SET, COMMON_WORDS word lists and structural heuristics.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const GAME_DIR = join(__dirname, '..', '..', '..');

// ====== Noise / filter data ======

const NOISE_SET = new Set([
  'hotel', 'room', 'floor', 'wall', 'door', 'pack', 'camera', 'light',
  'collider', 'audio', 'sprite', 'mesh', 'shader', 'material', 'texture',
  'canvas', 'panel', 'button', 'image', 'text', 'input', 'scroll', 'slider',
  'toggle', 'dropdown', 'animator', 'rig', 'bone', 'blend', 'clip',
  'navmesh', 'pathfinding', 'grid', 'layout', 'content', 'mask',
  'particle', 'trail', 'line', 'effect', 'postprocess', 'volume',
  'profile', 'asset', 'bundle', 'addressable', 'resource',
  'instance', 'prefab', 'variant', 'copy', 'clone',
]);

const COMMON_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
  'my', 'your', 'his', 'its', 'our', 'their',
  'this', 'that', 'these', 'those',
  'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'of', 'about',
  'and', 'or', 'but', 'if', 'because', 'so', 'while',
  'what', 'where', 'when', 'why', 'how', 'who', 'which',
  'do', 'does', 'did', 'done', 'doing',
  'have', 'has', 'had', 'having',
  'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must',
  'get', 'got', 'gotten', 'take', 'took', 'taken',
  'know', 'knew', 'known', 'think', 'thought',
  'want', 'need', 'like', 'look', 'see', 'saw', 'go', 'went', 'gone',
  'come', 'came', 'make', 'made', 'say', 'said', 'tell', 'told',
  'yes', 'no', 'ok', 'okay', 'please', 'thanks', 'thank',
  'not', 'no', 'don\'t', 'doesn\'t', 'didn\'t', 'won\'t', 'wouldn\'t',
  'can\'t', 'couldn\'t', 'shouldn\'t', 'isn\'t', 'aren\'t', 'wasn\'t',
  'weren\'t', 'haven\'t', 'hasn\'t', 'hadn\'t', 'ain\'t',
  'im', 'youre', 'hes', 'shes', 'its', 'we\'re', 'they\'re',
  'ive', 'you\'ve', 'we\'ve', 'they\'ve',
  'well', 'ill', 'youll', 'lets',
]);

// ====== Classification ======

export function isDialogue(str) {
  if (str.length < 12 || str.length > 500) return false;
  if (str.includes('_')) return false;
  if (str.includes('/')) return false;
  if (str.includes(':')) return false;
  if (/\.\w{2,4}$/.test(str)) return false;

  const words = str.toLowerCase().split(/\s+/);
  if (words.length < 3) return false;

  const alpha = (str.match(/[a-zA-Z]/g) || []).length;
  const lower = (str.match(/[a-z]/g) || []).length;
  if (alpha < 5 || lower < 3) return false;
  if (alpha / str.length < 0.35) return false;

  const commonCount = words.filter(w => COMMON_WORDS.has(w.replace(/[^a-z']/g, ''))).length;
  if (commonCount === 0 && !/[a-z][A-Z]/.test(str)) return false;

  const firstWord = words[0].replace(/[^a-z]/g, '');
  if (firstWord.length > 0 && NOISE_SET.has(firstWord)) return false;

  if (/\(\d+\)$/.test(str.trim())) return false;

  const uppercaseRatio = alpha > 0 ? (str.match(/[A-Z]/g) || []).length / alpha : 0;
  if (uppercaseRatio > 0.8 && lower < alpha * 0.5) return false;

  // Title-case with > 50% capitalized words = UI label, not dialogue
  const origWords = str.split(/\s+/);
  const upperStartWords = origWords.filter(w => /^[A-Z]/.test(w.replace(/[^a-zA-Z']/g, ''))).length;
  if (upperStartWords >= 2 && upperStartWords / origWords.length > 0.5) return false;

  return true;
}

export function isUI(str) {
  const s = str.trim();
  if (s.length < 2 || s.length > 80) return false;
  if (/[\x00-\x1f]/.test(s)) return false;

  // Reject strings with URLs or Windows file paths
  if (/\.\w{2,4}\/\w/.test(s) || /\\/.test(s)) return false;

  const upper = (s.match(/[A-Z]/g) || []).length;
  const lower = (s.match(/[a-z]/g) || []).length;
  const letters = upper + lower;

  if (letters < 2) return false;
  if (s.startsWith('_')) return false;

  // Contains path separator: "Save/Load" — UI before camelCase check
  if (s.includes('/')) return true;

  // Common camelCase UI words that should survive the camelCase reject
  const UI_CAMELCASE = new Set([
    'MainMenu', 'PauseMenu', 'StartMenu', 'OptionsMenu',
    'SubMenu', 'PopupMenu', 'DropDown', 'Dropdown', 'Tooltip',
    'Checkbox', 'CheckBox', 'RadioButton', 'ScrollBar', 'Scrollbar',
    'TextInput', 'TextArea', 'PasswordField',
    'OnClick', 'OnHover', 'OnFocus', 'OnSelect',
    'LoadGame', 'SaveGame', 'NewGame', 'QuickSave', 'QuickLoad',
    'AutoSave', 'ScreenShot', 'Screenshot',
  ]);
  if (UI_CAMELCASE.has(s)) return true;

  // Reject compound camelCase identifiers (Unity property names)
  // "OnPlay", "ImpactColor", "RainTintColor", "ListHolder"
  // Exception: "VSync" keeps uppercase V+S, "McFly" etc.
  if (!s.includes(' ') && !s.includes(':') && !s.includes('.') &&
      /[a-z][A-Z]/.test(s) && !/^[A-Z]{2,}[a-z]/.test(s)) {
    return false;
  }

  // All-caps: "MAIN MENU", "EXIT TO DESKTOP", "SAVE GAME", "FPS - Module"
  if (s === s.toUpperCase() && s !== s.toLowerCase()) {
    return letters >= 3;
  }

  // Sentence with period at end — likely dialogue, not UI
  if (/^[A-Z][a-z]+ .*\.$/.test(s) && (s.match(/\./g) || []).length === 1) return false;

  // Reject Unity ParticleSystem/Shuriken property patterns (multi-word tech names)
  const TECH_PROPERTY_PREFIXES = [
    'Start ', 'Rate ', 'Burst ', 'Gravity ', 'Max ', 'Min ', 'Impact ',
    'Speed ', 'Size ', 'Rotation ', 'Color ', 'Alpha ', 'Lifetime ',
    'Velocity ', 'Force ', 'Torque ', 'Noise ', 'UV ',
  ];
  if (TECH_PROPERTY_PREFIXES.some(p => s.startsWith(p))) return false;

  // Reject single PascalCase words that are technical
  const TECH_SINGLE_WORDS = new Set([
    'Awake', 'FixedUpdate', 'LateUpdate', 'OnEnable', 'OnDisable',
    'OnDestroy', 'OnTriggerEnter', 'OnTriggerStay', 'OnTriggerExit',
    'OnCollisionEnter', 'OnCollisionStay', 'OnCollisionExit',
    'OnMouseEnter', 'OnMouseOver', 'OnMouseExit', 'OnMouseDown',
    'OnMouseUp', 'OnGUI', 'OnDrawGizmos', 'Reset',
    'Lifetime', 'Start', 'Stop', 'Update',
  ]);
  if (TECH_SINGLE_WORDS.has(s)) return false;

  // Contains spaces: multi-word UI strings like "Enable VSync", "Dynamic Lighting"
  if (s.includes(' ')) {
    const words = s.split(/\s+/).filter(Boolean);
    const lowerStart = words.filter(w => /^[a-z]/.test(w)).length;
    // Allow max 1 lowercase-starting word (articles, prepositions)
    return lowerStart <= 1;
  }

  // Contains dot or colon: "Settings.FPSLimit", "Lovense: Enabled"
  // But not sentence-ending period (single period at end with 3+ words)
  if (s.includes(':')) return true;
  if (s.includes('.')) {
    // "Hello there." — sentence with period at end → not UI
    if (s.endsWith('.') && (s.match(/\./g) || []).length === 1 && (s.match(/\s+/g) || []).length >= 1) return false;
    return true;
  }

    // Single PascalCase word without internal camelCase: "Fullscreen", "Resolution"
    if (/^[A-Z][a-z]+$/.test(s) || /^[A-Z]+[a-z]+$/.test(s)) {
      // Common UI single words
      const UI_SINGLE_WORDS = new Set([
        'Off', 'Low', 'Med', 'Mid', 'Medium', 'High', 'Ultra', 'Slow', 'Normal', 'Fast',
        'On', 'Save', 'Load', 'Menu', 'Open', 'Close', 'Full', 'Max', 'Min',
        'Yes', 'No', 'Ok', 'OK', 'None', 'Auto', 'All', 'Any', 'Set',
        'Controls', 'Game', 'Video', 'Sound', 'Toys', 'Text',
        'Volume', 'Music', 'Effects', 'Voice', 'Sensitivity',
        'Resolution', 'Fullscreen', 'Display', 'Graphics', 'Quality',
        'Language', 'Dialogue', 'Autoplay', 'Sprint', 'Hints', 'Player',
        'Sprite', 'Profile', 'Privacy', 'Device', 'Search', 'Setup',
        'Port', 'Limited', 'Enabled', 'Disabled', 'Deactivated',
        'Category', 'Section', 'General', 'Advanced', 'Options',
        'Searching', 'MainMenu', 'Continue', 'Vibration', 'Apply',
        'Accept', 'Cancel', 'Confirm', 'Exit', 'Quit', 'Pause', 'Resume',
        'Retry', 'Back', 'Next', 'Prev', 'Previous', 'Submit', 'Reset',
        'Clear', 'Delete', 'Remove', 'Add', 'Edit', 'Rename', 'Copy',
        'Cut', 'Paste', 'Select', 'Deselect', 'Invert', 'Filter',
        'Sort', 'Refresh', 'Update', 'Install', 'Uninstall', 'Download',
        'Upload', 'Sync', 'Connect', 'Disconnect', 'Reconnect',
        'Bind', 'Unbind', 'Rebind', 'Assign', 'Unassign',
        'Key', 'Keys', 'Binding', 'Bindings', 'Keyboard', 'Mouse',
        'Touch', 'Tap', 'Click', 'Double', 'Hold', 'Press', 'Release',
        'Up', 'Down', 'Left', 'Right', 'Forward', 'Backward', 'Jump',
        'Crouch', 'Sneak', 'Run', 'Walk', 'Swim', 'Fly', 'Dive',
        'Attack', 'Defend', 'Guard', 'Block', 'Parry', 'Dodge',
        'Interact', 'Use', 'Equip', 'Unequip', 'Inventory', 'Backpack',
        'Map', 'Journal', 'Quest', 'Quests', 'Log', 'Codex', 'Bestiary',
        'Craft', 'Crafting', 'Cook', 'Brew', 'Enchant', 'Upgrade',
        'Repair', 'Buy', 'Sell', 'Trade', 'Shop', 'Store', 'Market',
        'Price', 'Cost', 'Value', 'Gold', 'Coin', 'Coins', 'Money',
        'Exp', 'XP', 'Level', 'Rank', 'Tier', 'Stage', 'Wave',
        'Score', 'Points', 'Time', 'Timer', 'Count', 'Total',
        'Attack', 'Damage', 'Defense', 'Armor', 'Health', 'Mana',
        'Stamina', 'Energy', 'Power', 'Speed', 'Agility', 'Strength',
        'Intelligence', 'Wisdom', 'Charisma', 'Luck', 'Faith',
        'Fire', 'Ice', 'Water', 'Earth', 'Wind', 'Lightning', 'Light',
        'Dark', 'Shadow', 'Holy', 'Unholy', 'Arcane', 'Nature',
        'Slash', 'Pierce', 'Blunt', 'Physical', 'Magical', 'Elemental',
        'Poison', 'Bleed', 'Burn', 'Freeze', 'Shock', 'Stun',
        'Sleep', 'Silence', 'Blind', 'Fear', 'Charm', 'Confuse',
        'Single', 'Multi', 'AoE', 'Self', 'Target', 'Random',
        'Ally', 'Ally', 'Enemy', 'Foe', 'Friend', 'Foe',
        'Party', 'Group', 'Solo', 'Team', 'Raid', 'Guild',
        'Chat', 'Message', 'Mail', 'Trade', 'Duel', 'Challenge',
        'Ranked', 'Casual', 'Competitive', 'Practice', 'Training',
        'Tutorial', 'Help', 'Guide', 'Info', 'Information',
        'About', 'Credits', 'License', 'Terms', 'Privacy',
        'Accessibility', 'Beta', 'Alpha', 'Demo', 'Trial', 'Full',
        'Connecting', 'Connected', 'Disconnected', 'Timeout',
        'Server', 'Client', 'Host', 'Join', 'Leave', 'Kick', 'Ban',
        'Mute', 'Unmute', 'Spectate', 'Observe',
        'Ready', 'Unready', 'Waiting', 'Countdown',
        'Victory', 'Defeat', 'Win', 'Lose', 'Draw',
        'Perfect', 'Excellent', 'Great', 'Good', 'Bad', 'Fail',
        'Complete', 'Incomplete', 'New', 'Old',
        'Online', 'Offline', 'Away', 'Busy', 'Idle', 'AFK',
        'Mod', 'Mods', 'DLC', 'Addon', 'Addons', 'Patch',
        'Notify', 'Notification', 'Alert', 'Warning', 'Error',
        'Success', 'Failure', 'Progress', 'Status',
        'Name', 'Title', 'Label', 'Tag', 'Icon', 'Badge',
        'List', 'Grid', 'Table', 'Tree', 'Tile', 'Card',
        'Top', 'Bottom', 'Middle', 'Center', 'Side', 'Edge',
        'Inside', 'Outside', 'Above', 'Below', 'Over', 'Under',
        'Show', 'Hide', 'Visible', 'Hidden', 'Reveal', 'Conceal',
        'Lock', 'Unlock', 'Locked', 'Unlocked',
        'Public', 'Private', 'Shared', 'Personal',
        'Free', 'Paid', 'Premium', 'Vip', 'VIP',
        'Guest', 'User', 'Admin', 'Owner', 'Member',
        'Male', 'Female', 'Other', 'Custom', 'Default',
        'Initial', 'Final', 'First', 'Last', 'Next', 'Previous',
        'Begin', 'End', 'Start', 'Stop', 'Finish',
        'Day', 'Night', 'Morning', 'Afternoon', 'Evening',
        'Today', 'Tomorrow', 'Yesterday',
      ]);
      if (UI_SINGLE_WORDS.has(s)) return true;

      // Other single PascalCase words → UI (buttons, tabs, etc.)
      return true;
    }

    return false;
}

/**
 * Classify a single string.
 * Returns 'dialogue', 'ui', or 'noise'.
 */
export function classify(str) {
  if (isDialogue(str)) return 'dialogue';
  if (isUI(str)) return 'ui';
  return 'noise';
}

// ====== Extraction ======

export function extractStrings(parsedJson, options = {}) {
  const { minLength = 10 } = options;
  const result = {
    dialogs: {},   // { file: [ {id, raw, offset}, ... ] }
    ui: {},
    noise: {},
    stats: { dialogue: 0, ui: 0, noise: 0 },
  };

  for (const file of parsedJson.files || []) {
    const fname = file.name;

    for (const s of file.strings || []) {
      if (!s.raw || s.raw.length < minLength) continue;
      const cls = classify(s.raw);

      if (cls === 'dialogue') {
        if (!result.dialogs[fname]) result.dialogs[fname] = [];
        result.dialogs[fname].push({ raw: s.raw, offset: s.offset });
      } else if (cls === 'ui') {
        if (!result.ui[fname]) result.ui[fname] = [];
        result.ui[fname].push({ raw: s.raw, offset: s.offset });
      } else {
        if (!result.noise[fname]) result.noise[fname] = [];
        result.noise[fname].push({ raw: s.raw, offset: s.offset });
      }
    }
  }

  // Sort each group by offset (preserves file order)
  for (const g of [result.dialogs, result.ui, result.noise]) {
    for (const arr of Object.values(g)) {
      arr.sort((a, b) => a.offset - b.offset);
    }
  }

  result.stats.dialogue = Object.values(result.dialogs).reduce((s, a) => s + a.length, 0);
  result.stats.ui = Object.values(result.ui).reduce((s, a) => s + a.length, 0);
  result.stats.noise = Object.values(result.noise).reduce((s, a) => s + a.length, 0);
  result.stats.total = result.stats.dialogue + result.stats.ui + result.stats.noise;

  return result;
}

/**
 * Write NDJSON lines per source file.
 *
 * Format per line: ["{source}_{seq}","{original}","","{offset}"]
 *
 * @param {object} groups  { sourceName: [ {raw, offset}, ... ] }
 * @param {string} outDir  output/dir/
 * @param {string} category 'dialogs' or 'ui'
 */
async function writeNDJSON(groups, outDir, category) {
  const dir = join(outDir, category);
  await mkdir(dir, { recursive: true });

  /**
   * Load existing translations from file, return Map<original, {id, translated}>
   */
  async function loadExisting(fp) {
    const map = new Map();
    try {
      const content = await readFile(fp, 'utf-8');
      for (const line of content.trim().split('\n').filter(Boolean)) {
        try {
          const [id, orig, trans] = JSON.parse(line);
          if (orig) map.set(orig, { id, translated: trans || '' });
        } catch { /* skip bad lines */ }
      }
    } catch { /* file not found */ }
    return map;
  }

  let total = 0;
  for (const [source, entries] of Object.entries(groups)) {
    if (entries.length === 0) continue;

    const fp = join(dir, `${source}.ndjson`);
    const existing = await loadExisting(fp);

    // Find max seq from existing entries for new ID generation
    let maxSeq = 0;
    for (const [, ex] of existing) {
      const m = ex.id.match(/_(\d+)$/);
      if (m) maxSeq = Math.max(maxSeq, parseInt(m[1], 10));
    }

    const seen = new Set();
    const lines = [];
    for (const e of entries) {
      if (seen.has(e.raw)) continue; // dedup within batch
      seen.add(e.raw);

      if (existing.has(e.raw)) {
        // Keep existing translation, preserve original ID
        const ex = existing.get(e.raw);
        lines.push(JSON.stringify([ex.id, e.raw, ex.translated, String(e.offset)]));
      } else {
        // New string — assign next ID, leave translation empty
        maxSeq++;
        const id = `${source}_${String(maxSeq).padStart(3, '0')}`;
        lines.push(JSON.stringify([id, e.raw, '', String(e.offset)]));
      }
    }

    await writeFile(fp, lines.join('\n') + '\n', 'utf-8');
    total += entries.length;
  }
  return total;
}

// ====== NDJSON reader ======

/**
 * Read NDJSON lines from a file.
 * Parser format: [offset, "raw"]
 */
async function readNDJSON(filepath) {
  const text = await readFile(filepath, 'utf-8');
  const lines = text.trim().split('\n').filter(Boolean);
  const strings = [];
  for (const line of lines) {
    try {
      const [offset, raw] = JSON.parse(line);
      strings.push({ offset, raw });
    } catch {
      // skip bad lines
    }
  }
  return strings;
}

// ====== CLI ======

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`Usage: node extractor.mjs [options]

Options:
  --input-dir <dir> Input NDJSON dir from parser (default: output/parser/)
  --out <dir>       Output directory (default: output/extractor/)
  --merge <dir>     Merge into translation dir (e.g. translations/ru/) — adds only new strings
  --min-len <N>     Minimum string length (default: 10)
  --detailed        Show per-file breakdown + samples
  --show-noise      Include noise strings in output
  --help, -h        Show this help

Output:
  dialogs/*.ndjson   — NDJSON: ["id","original","translated","offset"]
  ui/*.ndjson        — same format
  --merge: idempotent — existing translations preserved, only new strings added.
`);
    return;
  }

  const inputDir = args.includes('--input-dir')
    ? args[args.indexOf('--input-dir') + 1]
    : join(GAME_DIR, 'output', 'parser');

  const outDir = args.includes('--out')
    ? args[args.indexOf('--out') + 1]
    : join(GAME_DIR, 'output', 'extractor');

  const mergeDir = args.includes('--merge')
    ? args[args.indexOf('--merge') + 1]
    : null;

  const minLength = parseInt(args.includes('--min-len') ? args[args.indexOf('--min-len') + 1] : '3', 10);
  const detailed = args.includes('--detailed');
  const showNoise = args.includes('--show-noise');

  // Read manifest
  let manifest;
  try {
    manifest = JSON.parse(await readFile(join(inputDir, 'manifest.json'), 'utf-8'));
  } catch (err) {
    console.error(`Cannot read manifest: ${err.message}`);
    console.error('Run parser.mjs first to generate NDJSON files');
    process.exit(1);
  }

  // Read all NDJSON files from parser output
  const files = [];
  for (const f of manifest.files) {
    const ndjsonPath = join(inputDir, `${f.name}.ndjson`);
    try {
      const strings = await readNDJSON(ndjsonPath);
      files.push({ name: f.name, strings });
    } catch {
      console.error(`  warn: ${f.name}.ndjson not found, skipping`);
    }
  }

  // Build input structure matching old API
  const input = { files, totalStrings: manifest.totalStrings, totalFiles: files.length };

  console.error(`Extractor: processing ${input.totalStrings} strings from ${input.totalFiles} files\n`);

  const extracted = extractStrings(input, { minLength, detailed });

  console.error(`Dialogue: ${extracted.stats.dialogue}`);
  console.error(`UI:       ${extracted.stats.ui}`);
  console.error(`Noise:    ${extracted.stats.noise}`);
  console.error(`Total:    ${extracted.stats.total}`);
  console.error(`Filtered out: ${input.totalStrings - extracted.stats.total}`);

  const writeDir = mergeDir || outDir;
  await mkdir(writeDir, { recursive: true });

  const dialogCount = await writeNDJSON(extracted.dialogs, writeDir, 'dialogs');
  const uiCount = await writeNDJSON(extracted.ui, writeDir, 'ui');

  if (showNoise) {
    const noiseCount = await writeNDJSON(extracted.noise, writeDir, 'noise');
    console.error(`\nNoise files in ${writeDir}/noise/`);
  }

  const label = mergeDir ? 'Merged into' : 'Saved to';
  console.error(`\n${label} ${writeDir}/`);
  console.error(`  dialogs/: ${dialogCount} strings in ${Object.keys(extracted.dialogs).length} files`);
  console.error(`  ui/:      ${uiCount} strings in ${Object.keys(extracted.ui).length} files`);

  if (detailed) {
    // Show per-file breakdown
    console.error(`\nDialogs per file:`);
    for (const [src, arr] of Object.entries(extracted.dialogs).sort()) {
      console.error(`  ${src}.ndjson: ${arr.length}`);
    }
    console.error(`\nUI per file:`);
    for (const [src, arr] of Object.entries(extracted.ui).sort()) {
      console.error(`  ${src}.ndjson: ${arr.length}`);
    }

    if (extracted.stats.dialogue > 0) {
      console.error(`\nSample dialogue (10):`);
      const all = Object.entries(extracted.dialogs).flatMap(([f, arr]) =>
        arr.map(s => ({ file: f, ...s }))
      );
      for (const s of all.slice(0, 10)) {
        console.error(`  [${s.file}] ${s.raw}`);
      }
    }
  }
}

main().catch(console.error);
