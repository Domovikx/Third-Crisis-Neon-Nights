#!/usr/bin/env python3
"""
dump_assets.py — Dump Unity .assets files to structured JSON with real objects.

Использует UnityPy для чтения реальных Unity-объектов (Object Table + Type Tree + typed fields).
Дополнительно сканирует raw-байты каждого объекта на встроенные строки (диалоги, UI и т.д.).
Большие файлы разбиваются на чанки по OBJECTS_PER_CHUNK объектов.
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter

import UnityPy

DATA_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights\Third Crisis Neon Nights_Data"
)
GAME_DIR = DATA_DIR.parent

OBJECTS_PER_CHUNK = 5000
MAX_STRING_LEN = 500
MIN_RAW_LEN = 3

SKIP_ATTRS = {
    'assets_file', 'object_reader', 'container', 'files',
    'objects', 'resources', 'm_GameObject',
    'm_Script', 'm_Mesh', 'm_Material', 'm_Texture',
}

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


# ============================================================
# Discovery
# ============================================================

def discover_asset_files() -> list:
    files = []
    for i in range(16):
        p = DATA_DIR / f'level{i}'
        if p.exists():
            files.append((f'level{i}', p))
    for i in range(16):
        p = DATA_DIR / f'sharedassets{i}.assets'
        if p.exists():
            files.append((f'sharedassets{i}', p))
    seen = set()
    for name in ['resources.assets', 'globalgamemanagers.assets', 'globalgamemanagers']:
        p = DATA_DIR / name
        if p.exists():
            display = name.replace('.assets', '') if name.endswith('.assets') else name
            if display not in seen:
                seen.add(display)
                files.append((display, p))
    return files


def discover_bundle_files() -> list:
    """Find .bundle files in StreamingAssets/ recursively (AssetBundles)."""
    sa_dir = DATA_DIR / 'StreamingAssets'
    if not sa_dir.exists():
        return []
    files = []
    for p in sorted(sa_dir.rglob('*.bundle')):
        display = p.stem.replace('.bundle', '')
        if len(display) > 60:
            display = display[:60]
        files.append((f'bundle_{display}', p))
    return files


# ============================================================
# Raw string scanner (finds embedded text in object blobs)
# ============================================================

def scan_raw_strings(raw: bytes, base_offset: int = 0) -> list:
    """Scan raw bytes for readable strings and dialogue JSON."""
    results = []
    seen = set()
    n = len(raw)

    # 1. Null-terminated ASCII strings
    i = 0
    while i < n:
        if 32 <= raw[i] <= 126:
            start = i
            cur = bytearray()
            while i < n and 32 <= raw[i] <= 126:
                cur.append(raw[i])
                i += 1
            s = cur.decode('ascii', errors='replace').strip()
            if len(s) >= MIN_RAW_LEN:
                letters = sum(1 for c in s if c.isalpha())
                if letters >= 2:
                    key = (start, s)
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "offset": base_offset + start,
                            "text": s[:MAX_STRING_LEN],
                            "flags": "null_term",
                            "letters": letters,
                        })
        else:
            i += 1

    return results


def _extract_json_string(data: bytes, start: int):
    """Extract a JSON string starting after the opening quote. Handles escapes."""
    i = start
    raw = bytearray()
    while i < len(data):
        b = data[i]
        if b == 0x22:
            return raw.decode('utf-8', errors='replace'), i + 1
        elif b == 0x5C:
            if i + 1 < len(data):
                nxt = data[i + 1]
                if nxt in (0x22, 0x5C, 0x6E, 0x72, 0x74):
                    raw.append(nxt)
                    i += 2
                elif nxt == 0x75:
                    if i + 5 < len(data):
                        try:
                            hex_str = data[i+2:i+6].decode('ascii')
                            raw.extend(chr(int(hex_str, 16)).encode('utf-8'))
                            i += 6
                        except Exception:
                            i += 2
                    else:
                        i += 2
                else:
                    raw.append(nxt)
                    i += 2
            else:
                break
        else:
            raw.append(b)
            i += 1
    return None, i


def parse_dialogue_from_raw(raw: bytes, base_offset: int = 0) -> list:
    """Extract Speaker/Text pairs from JSON dialogue pattern."""
    results = []
    seen = set()
    marker = b'"Speaker":"'
    text_marker = b',"Text":"'

    i = 0
    while i < len(raw):
        pos = raw.find(marker, i)
        if pos < 0:
            break

        speaker, sp_end = _extract_json_string(raw, pos + len(marker))
        if speaker is None:
            i = pos + 1
            continue

        text_pos = raw.find(text_marker, sp_end)
        if text_pos < 0:
            i = sp_end
            continue

        text, tx_end = _extract_json_string(raw, text_pos + len(text_marker))
        if text is None:
            i = text_pos + 1
            continue

        clean = re.sub(r'<[^>]+>', '', text).strip()
        key = f"{speaker}|{clean}"
        if clean and key not in seen:
            seen.add(key)
            results.append({
                "offset": base_offset + pos,
                "speaker": speaker,
                "text": clean[:MAX_STRING_LEN],
                "rich_text": text[:MAX_STRING_LEN],
            })

        i = tx_end

    return results


# ============================================================
# Object extraction
# ============================================================

def _is_skip_prefix(s: str) -> bool:
    return any(s.startswith(p) for p in SKIP_RAW_PREFIXES)


def _strip_rich(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s).strip()


def parse_playmaker_dialogues(raw_strings: list) -> list:
    """Extract dialogue lines from PlayMaker FSM raw_strings (line_X pattern)."""
    results = []
    seen = set()

    i = 0
    while i < len(raw_strings):
        s = raw_strings[i].strip()
        if not s.startswith('line_'):
            i += 1
            continue

        # Skip line_X marker and optional duplicate
        i += 1
        if i < len(raw_strings) and raw_strings[i].strip() == s:
            i += 1

        # Find dialogue text: next non-skip string with space, length > 3
        text = ""
        while i < len(raw_strings):
            ns = raw_strings[i].strip()
            if _is_skip_prefix(ns) or ns == '':
                i += 1
                continue
            if len(ns) <= 3 or ' ' not in ns:
                i += 1
                continue
            if ns.startswith('{') or ns.startswith('['):
                i += 1
                continue
            text = ns
            i += 1
            break

        if not text:
            continue

        clean = _strip_rich(text)
        rich_text = text if text != clean else ""

        # Try to find speaker after the text
        speaker = ""
        if i < len(raw_strings):
            ns = raw_strings[i].strip()
            if (ns and not _is_skip_prefix(ns) and not ns.startswith('line_')
                    and ' ' not in ns and ns[0].isupper() and ns.isalpha()
                    and ns not in KNOWN_NON_SPEAKERS):
                speaker = ns
                i += 1

        key = f"{speaker}|{clean}"
        if clean and key not in seen:
            seen.add(key)
            results.append({
                "speaker": speaker,
                "text": clean,
                "rich_text": rich_text,
            })

    return results


def pptr_to_dict(pptr) -> dict:
    try:
        return {"file_id": pptr.m_FileID, "path_id": pptr.m_PathID}
    except Exception:
        return str(pptr)


def _serialize_list(val) -> list | None:
    if len(val) == 0:
        return []
    try:
        first = val[0]
    except Exception:
        return None
    ft = type(first).__name__
    if ft in ('int', 'float', 'str', 'bool'):
        return [v for v in val]
    if hasattr(first, 'm_FileID') and hasattr(first, 'm_PathID'):
        items = []
        for v in val:
            try:
                items.append(pptr_to_dict(v))
            except Exception:
                items.append(str(v))
        return items
    return None


def extract_object(obj, env) -> dict:
    """Extract typed fields + raw strings from a Unity object."""
    entry = {
        "path_id": obj.path_id,
        "type": obj.type.name,
    }

    # --- Typed fields ---
    try:
        data = obj.read()
    except Exception:
        entry["error"] = "read_failed"
    else:
        string_fields = {}
        other_fields = {}

        for attr in sorted(dir(data)):
            if attr.startswith('_') or attr in SKIP_ATTRS:
                continue
            if callable(getattr(data, attr, None)):
                continue
            try:
                val = getattr(data, attr)
            except Exception:
                continue
            if val is None:
                continue
            tname = type(val).__name__

            if isinstance(val, str):
                if val:
                    string_fields[attr] = val[:MAX_STRING_LEN]
                continue
            if hasattr(val, 'm_FileID') and hasattr(val, 'm_PathID'):
                other_fields[attr] = pptr_to_dict(val)
                continue
            if isinstance(val, (list, tuple)):
                items = _serialize_list(val)
                if items is not None:
                    other_fields[attr] = items
                continue
            if isinstance(val, (int, float, bool)):
                other_fields[attr] = val
                continue
            if tname.startswith('Enum'):
                other_fields[attr] = str(val)
                continue

        if string_fields:
            entry["strings"] = string_fields
        if other_fields:
            entry["fields"] = other_fields

    # --- Raw bytes scan ---
    try:
        raw = obj.get_raw_data()
    except Exception:
        return entry

    raw_strings = scan_raw_strings(raw)
    all_texts = [s["text"] for s in raw_strings]
    dialogues = parse_dialogue_from_raw(raw)
    playmaker = parse_playmaker_dialogues(all_texts)
    if playmaker:
        dialogues.extend(playmaker)
    if dialogues:
        entry["dialogues"] = dialogues
    if raw_strings:
        entry["raw_strings"] = all_texts[:100]

    return entry


# ============================================================
# Global strings scan (Settings keys, UI text outside objects)
# ============================================================

def scan_settings_keys(data: bytes) -> list:
    """Scan raw asset bytes for Settings.X key+display pairs."""
    results = []
    seen_keys = set()
    i = 0
    while i < len(data):
        pos = data.find(b'Settings.', i)
        if pos < 0:
            break
        if pos < 4:
            i = pos + 1
            continue
        key_len = int.from_bytes(data[pos-4:pos], 'little')
        if 9 <= key_len <= 60:
            key = data[pos:pos+key_len].decode('ascii', errors='replace')
            if key.startswith('Settings.') and len(key) > 9:
                after_key = pos + key_len
                while after_key < len(data) and data[after_key] == 0:
                    after_key += 1
                if after_key + 4 < len(data):
                    disp_len = int.from_bytes(data[after_key:after_key+4], 'little')
                    if 1 <= disp_len <= 100:
                        disp = data[after_key+4:after_key+4+disp_len].decode('utf-8', errors='replace')
                        if disp and key not in seen_keys:
                            seen_keys.add(key)
                            results.append({"key": key, "display": disp[:MAX_STRING_LEN]})
        i = pos + 1
    return results


def _is_global_string_candidate(s: str) -> bool:
    """Check if a string from non-object data looks like UI text."""
    # Must have letters
    letters = sum(1 for c in s if c.isalpha())
    if letters < 3:
        return False
    # Reject strings with code symbols
    if any(c in s for c in '#$%@&*{}[]()<>|^~`='):
        return False
    # Reject hex-like strings (random uppercase+digits)
    if all(c.isupper() or c.isdigit() or c in ' ' for c in s):
        if len(s) >= 3 and not any(c in 'AEIOUY ' for c in s.upper()):
            return False
    # Accept multi-word strings
    if ' ' in s:
        return True
    # Accept all-caps with vowels (MENU, FULLSCREEN)
    if s.isupper():
        return any(v in s for v in 'AEIOU')
    # Accept PascalCase (first upper, rest lower)
    if s[0].isupper() and any(c.islower() for c in s[1:]):
        return letters >= 4
    # Accept mixed case with letters and punctuation
    if letters >= 6:
        return True
    return False


def scan_global_strings(data: bytes) -> list:
    """Find readable UI-like strings in non-object data."""
    results = []
    seen = set()
    n = len(data)
    i = 0
    while i < n:
        if 32 <= data[i] <= 126:
            start = i
            cur = bytearray()
            while i < n and 32 <= data[i] <= 126:
                cur.append(data[i])
                i += 1
            s = cur.decode('ascii', errors='replace').strip()
            if 4 <= len(s) <= 120:
                if s not in seen and _is_global_string_candidate(s):
                    seen.add(s)
                    results.append(s)
        else:
            i += 1
    return results


def get_object_ranges(env) -> list:
    """Extract (data_offset, absolute_offset, size) for all objects."""
    ranges = []
    try:
        for assets_file in env.files.values():
            if hasattr(assets_file, 'objects'):
                data_offset = getattr(assets_file, 'data_offset', 0)
                for obj in assets_file.objects.values():
                    if hasattr(obj, 'offset') and hasattr(obj, 'size'):
                        abs_off = data_offset + obj.offset
                        ranges.append((abs_off, abs_off + obj.size, obj.path_id))
    except Exception:
        pass
    return ranges


# ============================================================
# JSON output with chunking
# ============================================================

def write_asset_json(name: str, env, out_dir: Path, raw_data: bytes = None):
    all_objs = list(env.objects)
    total = len(all_objs)
    num_chunks = (total + OBJECTS_PER_CHUNK - 1) // OBJECTS_PER_CHUNK

    type_counts = Counter(obj.type.name for obj in all_objs)

    # Collect already-found strings for dedup
    found_texts = set()

    # Summary
    summary = {
        "asset": name,
        "chunk": "summary",
        "total_chunks": num_chunks,
        "total_objects": total,
        "object_types": dict(type_counts.most_common()),
        "chunks": [
            {
                "chunk": ci,
                "file": f"{name}.chunk{ci:03d}.json",
                "objects": min(OBJECTS_PER_CHUNK, total - ci * OBJECTS_PER_CHUNK),
                "range": f"{ci * OBJECTS_PER_CHUNK}–{min(ci * OBJECTS_PER_CHUNK + OBJECTS_PER_CHUNK - 1, total - 1)}",
            }
            for ci in range(num_chunks)
        ],
    }

    # --- Global strings scan ---
    if raw_data:
        settings = scan_settings_keys(raw_data)
        if settings:
            summary["settings_keys"] = settings
            for s in settings:
                found_texts.add(s["key"])
                found_texts.add(s["display"])

        global_strings = scan_global_strings(raw_data)
        global_strings = [t for t in global_strings if t not in found_texts][:200]
        if global_strings:
            summary["global_strings"] = global_strings

    (out_dir / f"{name}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(f"  -> {out_dir / f'{name}.json'} (summary, {total} objects)", file=sys.stderr)

    # Chunks
    for ci in range(num_chunks):
        cstart = ci * OBJECTS_PER_CHUNK
        cend = min(cstart + OBJECTS_PER_CHUNK, total)
        chunk_data = {
            "asset": name,
            "chunk": ci,
            "total_chunks": num_chunks,
            "objects": [],
        }
        for obj in all_objs[cstart:cend]:
            try:
                extracted = extract_object(obj, env)
            except Exception:
                extracted = {"path_id": obj.path_id, "type": obj.type.name,
                             "error": "extract_failed"}
            chunk_data["objects"].append(extracted)

        try:
            (out_dir / f"{name}.chunk{ci:03d}.json").write_text(
                json.dumps(chunk_data, indent=2, ensure_ascii=False), encoding='utf-8'
            )
        except Exception as e:
            print(f"    WARN: chunk {ci} write failed: {e}", file=sys.stderr)

    total_files = 1 + num_chunks
    print(f"  -> {num_chunks} chunk(s)" if total_files > 2
          else f"  -> {out_dir / f'{name}.chunk000.json'}", file=sys.stderr)
    return total_files


# ============================================================
# Index
# ============================================================

def format_index_md(results: list) -> str:
    lines = [
        "# Asset Dump Index (UnityPy)\n",
        "| File | Objects | Chunks |",
        "|------|---------|--------|",
    ]
    for name, total_objs, nfiles in sorted(results, key=lambda x: x[0]):
        lines.append(f"| [{name}]({name}.json) | {total_objs} | {nfiles - 1} |")
    return '\n'.join(lines) + '\n'


# ============================================================
# Main
# ============================================================

def dump_assets(output_dir: str = None) -> str:
    out = Path(output_dir) if output_dir else (GAME_DIR / 'dump_assets')
    out.mkdir(parents=True, exist_ok=True)

    files = discover_asset_files()
    bundle_files = discover_bundle_files()
    if bundle_files:
        print(f"  Bundles: {len(bundle_files)} file(s) found", file=sys.stderr)
    files.extend(bundle_files)
    print(f"Dump-Assets (UnityPy): {len(files)} file(s) found", file=sys.stderr)

    results = []
    for name, fp in files:
        print(f"  Loading {name}...", file=sys.stderr)
        try:
            raw_data = fp.read_bytes()
            env = UnityPy.load(str(fp))
            total_objs = len(env.objects)
            print(f"    -> {total_objs} objects", file=sys.stderr)
            nfiles = write_asset_json(name, env, out, raw_data)
            results.append((name, total_objs, nfiles))
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)

    (out / 'index.md').write_text(format_index_md(results), encoding='utf-8')
    print(f"  -> {out / 'index.md'}", file=sys.stderr)
    print(f"\nDone: {len(results)} assets -> {out}", file=sys.stderr)
    return str(out)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else None
    dump_assets(out_dir)
