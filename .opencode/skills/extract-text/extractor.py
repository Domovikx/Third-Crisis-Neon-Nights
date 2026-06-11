#!/usr/bin/env python3
"""
extractor.py — Извлекает диалоги, UI-строки и имена персонажей из dump_assets/
и пишет YAML-файлы переводов в объектном формате.

Работает через dump_assets/ — не сканирует бинарники напрямую.

Файлы на выходе (в translations/):
  - dialogues.{path_id}.yaml  — ANToolkit JSON диалоги
   - dialogues.bundle_*.yaml   — PlayMaker FSM диалоги (по активу)
  - speakers.yaml             — персонажи
  - settings_keys.yaml        — UI-строки

Объектный формат:
  dialogues: {text, translation, speaker, rich_text, rich_translation}
  speakers:  {text, translation, gender, notes}
  settings:  {text, translation}
"""

import sys
import json
import re
import yaml
from pathlib import Path
from collections import OrderedDict

GAME_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights"
)
DUMP_DIR = GAME_DIR / "dump_assets"
OUT_DIR = GAME_DIR / "translations"


def _dialogues_dir() -> Path:
    return OUT_DIR / "dialogues"

DIALOGUE_FIELDS = ["text", "translation", "speaker", "rich_text", "rich_translation"]
SPEAKER_FIELDS = ["text", "translation", "gender", "notes"]
SETTINGS_FIELDS = ["text", "translation"]


def find_chunks() -> list:
    return sorted(DUMP_DIR.glob("*.chunk*.json"))


def find_summaries() -> list:
    return sorted(f for f in DUMP_DIR.glob("*.json") if ".chunk" not in f.name)


def extract_dialogues(chunk_files: list) -> dict:
    """Scan all chunk files for objects with dialogues field.
    Returns dict: path_id -> [dict, ...]"""
    by_pid = {}
    for fp in chunk_files:
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue
        for obj in data.get("objects", []):
            pid = obj.get("path_id")
            if pid is None:
                continue
            raw = obj.get("dialogues", [])
            if not raw:
                continue
            entries = by_pid.setdefault(pid, [])
            seen = set()
            for d in raw:
                text = d.get("text", "").strip()
                speaker = d.get("speaker", "").strip()
                rich_text = _resolve_named_colors(d.get("rich_text", "").strip())
                if not text:
                    continue
                key = (text, speaker)
                if key not in seen:
                    seen.add(key)
                    entries.append({
                        "text": text,
                        "translation": "",
                        "speaker": speaker,
                        "rich_text": rich_text,
                        "rich_translation": "",
                    })
    return by_pid


SKIP_RAW_PREFIXES = (
    'line_', 'expressions/', 'separatedexpressions/', 'Poses/',
    'expressionadditive/', 'p>xo', 'Other Dialogue Presets',
    'Zoey Dialogue Presets', '_Preset', 'Dialogue Presets',
    'Char_', 'Apl_',
)

KNOWN_NON_SPEAKERS = {
    'GlowingHole', 'GlowingHoleKeys/', 'Narrator', 'Confirm',
    'Other Dialogue Presets', 'Zoey Dialogue Presets', 'Simon',
}

_RICH_TAG_RX = re.compile(r'<[^>]+>')
_BUNDLE_HASH_RX = re.compile(r'_(?:assets|scenes)_all_[a-f0-9]+$')

_NAMED_COLOR_RX = re.compile(r'<color=(\w+)>')


def _load_color_parser_list() -> dict:
    """Scan all chunk dumps for color_parser_list entries and merge into one dict."""
    result = {}
    if not DUMP_DIR.exists():
        return result
    for fp in sorted(DUMP_DIR.glob("*.chunk*.json")):
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue
        for obj in data.get("objects", []):
            cpl = obj.get("color_parser_list")
            if isinstance(cpl, dict):
                result.update(cpl)
    return result


_COLOR_NAME_TO_HEX = _load_color_parser_list()


def _bundle_short_name(asset_name: str) -> str:
    """Derive stable short filename from bundle asset name (strip variable hash suffix)."""
    return _BUNDLE_HASH_RX.sub('', asset_name)


def _is_skip_prefix(s: str) -> bool:
    return any(s.startswith(p) for p in SKIP_RAW_PREFIXES)


def _resolve_named_colors(s: str) -> str:
    return _NAMED_COLOR_RX.sub(lambda m: f'<color={_COLOR_NAME_TO_HEX.get(m.group(1), m.group(1))}>', s)

def _strip_rich(s: str) -> str:
    return _RICH_TAG_RX.sub('', s).strip()


def extract_bundle_dialogues(chunk_files: list) -> dict:
    """Extract dialogue texts from bundle PlayMaker FSM raw_strings.
    Returns dict: bundle_name -> [dict, ...]
    """
    by_bundle = {}
    seen_entries = set()

    for fp in chunk_files:
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue

        asset_name = data.get("asset", "")
        if not asset_name.startswith("bundle_"):
            continue

        if asset_name not in by_bundle:
            by_bundle[asset_name] = []

        for obj in data.get("objects", []):
            rs = obj.get("raw_strings", [])
            if not rs:
                continue

            has_line = any(s.startswith("line_") for s in rs)
            if not has_line:
                continue

            obj_name = obj.get("strings", {}).get("m_Name", "")

            i = 0
            while i < len(rs):
                s = rs[i].strip()

                if _is_skip_prefix(s) or s == obj_name:
                    i += 1
                    continue

                if len(s) <= 3 or ' ' not in s:
                    i += 1
                    continue

                if s.startswith('{') or s.startswith('['):
                    i += 1
                    continue

                clean = _strip_rich(s)
                if not clean or len(clean) < 4:
                    i += 1
                    continue

                rich_text = _resolve_named_colors(s) if s != clean else ""

                speaker = ""
                if i + 1 < len(rs):
                    ns = rs[i + 1].strip()
                    if (ns and not _is_skip_prefix(ns) and not ns.startswith('line_')
                            and ns != obj_name and ' ' not in ns
                            and ns[0].isupper() and ns.isalpha()
                            and ns not in KNOWN_NON_SPEAKERS):
                        speaker = ns
                        i += 1

                entry_key = (clean, speaker)
                if entry_key not in seen_entries:
                    seen_entries.add(entry_key)
                    entry = {
                        "text": clean,
                        "translation": "",
                        "speaker": speaker,
                        "rich_text": rich_text,
                        "rich_translation": "",
                    }
                    by_bundle[asset_name].append(entry)

                i += 1

    return by_bundle


def extract_global_strings(summary_files: list) -> list:
    """Extract UI strings from settings_keys.
    Returns list of dicts with text + translation."""
    seen = set()
    keys = []
    for fp in summary_files:
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue
        for sk in data.get("settings_keys", []):
            display = sk.get("display", "").strip().strip("\x00")
            if not display or display in seen or "\x00" in display:
                continue
            seen.add(display)
            keys.append({"text": display, "translation": ""})
    return keys


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

_ALWAYS_FIELDS = {"text", "translation"}


def _format_entry(entry: dict) -> str:
    """Format a dict as YAML block entry. Skip empty optional fields."""
    rich_text = entry.get("rich_text", "")
    has_rich = bool(rich_text) and rich_text != entry.get("text", "")
    keys = []
    for k in entry:
        if k in _ALWAYS_FIELDS:
            keys.append(k)
        elif k in ("rich_text", "rich_translation"):
            if has_rich:
                keys.append(k)
        elif entry[k]:
            keys.append(k)
    if not keys:
        return ""
    # Build YAML manually with reliable value quoting
    def _qv(v: str) -> str:
        """Quote a string value for YAML. Always quote to ensure safe re-parsing."""
        if not v:
            return '""'
        escaped = v.replace('\\', '\\\\').replace('"', '\\"')
        # Strip control chars except newline/carriage return
        escaped = "".join(c for c in escaped if c >= " " or c in "\n\r")
        return f'"{escaped}"'
    
    parts = [f"{k}: {_qv(entry[k])}" for k in keys]
    dumped = "\n".join(parts)
    lines = dumped.strip().splitlines()
    if not lines:
        return ""
    first = lines[0]
    rest = [f"  {line}" if not line.startswith("  ") else line for line in lines[1:]]
    return "\n".join([first] + rest)


def _normalize_entry(entry, fields: list) -> dict:
    """Convert a list or dict entry to a dict with the given schema."""
    if isinstance(entry, dict):
        return {f: entry.get(f, "") for f in fields}
    if isinstance(entry, list):
        return {fields[i]: entry[i] if i < len(entry) else "" for i in range(len(fields))}
    return {}


_YAML_LINE_RX = re.compile(
    r'^(\s*)([\w_]+):\s*'
    r'(?:"((?:[^"\\]|\\.)*)"'   # double-quoted
    r"|'((?:[^'\\]|\\.)*)'"     # single-quoted
    r'|(\S.*))$'                 # unquoted
)


def _unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")


def _parse_yaml_fallback(content: str) -> list:
    """Fallback line-by-line YAML parser for malformed files.
    Handles quoted and unquoted values. Returns list of dicts."""
    entries = []
    current = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        # Blank or comment: end current entry
        if not line or line.startswith("#"):
            if current is not None:
                entries.append(current)
                current = None
            continue
        # Check if line has key:value pattern
        # Handle line that looks like "  key: value" (continuation) or "- key: value" (list item start)
        stripped_for_match = line
        if line.startswith("- "):
            stripped_for_match = line[2:]
        m = _YAML_LINE_RX.match(stripped_for_match)
        if m:
            key = m.group(2)
            val = m.group(3) or m.group(4) or m.group(5) or ""
            val = val.strip().rstrip(',')
            # Strip leading/trailing mismatched quotes from unquoted match (malformed YAML)
            if not m.group(3) and not m.group(4):
                val = val.lstrip('"').lstrip("'").rstrip('"').rstrip("'")
            val = _unescape(val)
            if line.startswith("- ") or current is None:
                # New entry
                if current is not None:
                    entries.append(current)
                current = {key: val}
            else:
                # Continuation of current entry
                current[key] = val
    if current is not None:
        entries.append(current)
    return entries


def read_yaml(path: Path) -> list:
    """Read existing YAML entries. Returns [] if file missing or empty."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # Fallback: try line-by-line parser
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return _parse_yaml_fallback(content)
    except Exception:
        return []


def _auto_rich_translation(entry: dict) -> dict:
    """Auto-generate rich_translation from rich_text + translation if missing.
    No-op if rich_text equals text (no rich formatting)."""
    rich = entry.get('rich_text', '')
    if not rich or rich == entry.get('text', ''):
        return entry
    if not entry.get('rich_translation') and entry.get('translation'):
        plain = _RICH_TAG_RX.sub('', rich).strip()
        if plain and plain in rich:
            entry['rich_translation'] = rich.replace(plain, entry['translation'])
    return entry


def _normalize_rich(entry: dict) -> dict:
    """Resolve named colors in rich_text and rich_translation."""
    if entry.get("rich_text"):
        entry["rich_text"] = _resolve_named_colors(entry["rich_text"])
    if entry.get("rich_translation"):
        entry["rich_translation"] = _resolve_named_colors(entry["rich_translation"])
    return entry


def merge(existing_raw: list, fresh: list, fields: list, *key_fields: str) -> list:
    """Merge existing translations into fresh entries.
    existing_raw: raw list from read_yaml (lists or dicts)
    fresh: list of dicts from extraction
    fields: schema field names
    key_fields: field names that form unique key (e.g. 'text', 'speaker')
    """
    if not existing_raw:
        return fresh

    existing = [_normalize_entry(e, fields) for e in existing_raw]
    old_map = {}
    for e in existing:
        k = tuple(e.get(f, "") for f in key_fields)
        if not k[0]:
            continue
        old_map[k] = e

    # Fields that must always come from fresh dump data, never from old (game data, not user content)
    _always_fresh = {"rich_text"}
    
    merged = []
    for e in fresh:
        k = tuple(e.get(f, "") for f in key_fields)
        if k in old_map:
            old = old_map[k]
            new = dict(e)
            for fld in fields:
                if fld not in key_fields and fld not in _always_fresh and old.get(fld):
                    new[fld] = old[fld]
            merged.append(_normalize_entry(new, fields))
        else:
            merged.append(_normalize_entry(e, fields))
    return merged


def write_yaml(path: Path, data: list, header: str = None):
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    if header:
        lines.append(f"# {header}")
        lines.append("")
    for entry in data:
        if not isinstance(entry, dict):
            continue
        lines.append("- " + _format_entry(entry))
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  -> {path} ({len(data)} entries)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract():
    print("Extractor: reading dump_assets/...", file=sys.stderr)

    chunks = find_chunks()
    summaries = find_summaries()
    print(f"  chunks: {len(chunks)}, summaries: {len(summaries)}", file=sys.stderr)

    by_pid = extract_dialogues(chunks)
    by_bundle = extract_bundle_dialogues(chunks)

    _dialogues_dir().mkdir(parents=True, exist_ok=True)

    total = 0
    for pid in sorted(by_pid):
        fpath = _dialogues_dir() / f"{pid}.yaml"
        existing = read_yaml(fpath)
        merged = [_normalize_rich(_auto_rich_translation(e)) for e in merge(existing, by_pid[pid], DIALOGUE_FIELDS, "text", "speaker")]
        total += len(merged)
        write_yaml(fpath, merged, header=f"Dialogues (path_id={pid})")

    # Build set of (text, speaker) already covered by ANToolkit dialogues
    dialogue_keys = set()
    for pid in sorted(by_pid):
        fpath = _dialogues_dir() / f"{pid}.yaml"
        for e in read_yaml(fpath):
            k = (e.get("text", ""), e.get("speaker", ""))
            if k[0]:
                dialogue_keys.add(k)

    # Write one YAML per bundle asset (stable short name, no hash)
    for asset_name, entries in by_bundle.items():
        entries = [e for e in entries if (e["text"], e.get("speaker", "")) not in dialogue_keys]
        if not entries:
            continue
        short = _bundle_short_name(asset_name)
        fpath = _dialogues_dir() / f"bundle.{short}.yaml"
        merged = [_normalize_rich(_auto_rich_translation(e)) for e in merge(read_yaml(fpath), entries, DIALOGUE_FIELDS, "text", "speaker")]
        total += len(merged)
        write_yaml(fpath, merged, header=f"Dialogues (bundle: {asset_name})")

    all_speakers = OrderedDict()
    for entries in by_pid.values():
        for d in entries:
            sp = d.get("speaker", "")
            if sp and sp not in all_speakers:
                all_speakers[sp] = True
    for entries in by_bundle.values():
        for d in entries:
            sp = d.get("speaker", "")
            if sp and sp not in all_speakers:
                all_speakers[sp] = True

    fpath = OUT_DIR / "speakers.yaml"
    speakers_list = [
        {"text": sp, "translation": "", "gender": "", "notes": ""}
        for sp in all_speakers
    ]
    speakers_list = merge(read_yaml(fpath), speakers_list, SPEAKER_FIELDS, "text")
    write_yaml(fpath, speakers_list, header="Speakers")

    fpath = OUT_DIR / "settings_keys.yaml"
    settings_keys = extract_global_strings(summaries)
    settings_keys = merge(read_yaml(fpath), settings_keys, SETTINGS_FIELDS, "text")
    write_yaml(fpath, settings_keys, header="Settings keys")

    print(f"\nDone: {total} dialogues across "
          f"{len(by_pid)} .assets sources + {len(by_bundle)} bundles, "
          f"{len(speakers_list)} speakers, {len(settings_keys)} settings keys",
          file=sys.stderr)


if __name__ == "__main__":
    extract()
