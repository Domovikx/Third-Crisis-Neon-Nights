#!/usr/bin/env python3
"""
extractor.py — Извлекает диалоги, UI-строки и имена персонажей из dump_assets/
и пишет YAML-файлы переводов в объектном формате.

Работает через dump_assets/ — не сканирует бинарники напрямую.

Файлы на выходе (в translations/):
  - dialogues.{path_id}.yaml  — ANToolkit JSON диалоги
  - dialogues.bundle.yaml     — PlayMaker FSM диалоги
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
                rich_text = d.get("rich_text", "").strip()
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


def _is_skip_prefix(s: str) -> bool:
    return any(s.startswith(p) for p in SKIP_RAW_PREFIXES)


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
                    by_bundle[asset_name].append({
                        "text": clean,
                        "translation": "",
                        "speaker": speaker,
                    })

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

def _fmt(s: str) -> str:
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = "".join(c for c in s if c >= " " or c in "\n\r")
    return f'"{s}"'


def _format_entry(entry: dict) -> str:
    """Format a dict as YAML block entry. All fields written (incl. empty)."""
    keys = list(entry.keys())
    if not keys:
        return ""
    first = keys[0]
    parts = [f"{first}: {_fmt(entry[first])}"]
    parts += [f"  {k}: {_fmt(entry[k])}" for k in keys[1:]]
    return "\n".join(parts)


def _normalize_entry(entry, fields: list) -> dict:
    """Convert a list or dict entry to a dict with the given schema."""
    if isinstance(entry, dict):
        return {f: entry.get(f, "") for f in fields}
    if isinstance(entry, list):
        return {fields[i]: entry[i] if i < len(entry) else "" for i in range(len(fields))}
    return {}


def read_yaml(path: Path) -> list:
    """Read existing YAML entries. Returns [] if file missing or empty."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    return data


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

    merged = []
    for e in fresh:
        k = tuple(e.get(f, "") for f in key_fields)
        if k in old_map:
            old = old_map[k]
            new = dict(e)
            for fld in fields:
                if fld not in key_fields and old.get(fld):
                    new[fld] = old[fld]
            merged.append(new)
        else:
            merged.append(e)
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

    total = 0
    for pid in sorted(by_pid):
        fpath = OUT_DIR / f"dialogues.{pid}.yaml"
        existing = read_yaml(fpath)
        merged = merge(existing, by_pid[pid], DIALOGUE_FIELDS, "text", "speaker")
        total += len(merged)
        write_yaml(fpath, merged, header=f"Dialogues (path_id={pid})")

    bundle_entries = []
    seen_bundle = set()
    for entries in by_bundle.values():
        for e in entries:
            k = (e["text"], e.get("speaker", ""))
            if k not in seen_bundle:
                seen_bundle.add(k)
                bundle_entries.append(e)
    if bundle_entries:
        fpath = OUT_DIR / "dialogues.bundle.yaml"
        bundle_entries = merge(read_yaml(fpath), bundle_entries, DIALOGUE_FIELDS, "text", "speaker")
        total += len(bundle_entries)
        write_yaml(fpath, bundle_entries, header="Dialogues (bundle/FSM)")

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
