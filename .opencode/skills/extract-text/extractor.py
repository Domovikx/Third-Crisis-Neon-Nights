#!/usr/bin/env python3
"""
extractor.py — Извлекает диалоги, UI-строки и имена персонажей из dump_assets/
и пишет YAML-файлы переводов.

Работает через dump_assets/ — не сканирует бинарники напрямую.

Файлы на выходе (в translations/):
  - dialogues.{path_id}.yaml:  диалоги по источнику  [text, translation, speaker]
  - speakers.yaml:             персонажи             [name, translation, gender]
  - settings_keys.yaml:        UI-строки             [key, translation]
"""

import sys
import json
import yaml
from pathlib import Path
from collections import OrderedDict

GAME_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights"
)
DUMP_DIR = GAME_DIR / "dump_assets"
OUT_DIR = GAME_DIR / "translations"


def find_chunks() -> list:
    return sorted(DUMP_DIR.glob("*.chunk*.json"))


def find_summaries() -> list:
    return sorted(f for f in DUMP_DIR.glob("*.json") if ".chunk" not in f.name)


def extract_dialogues(chunk_files: list) -> dict:
    """Scan all chunk files for objects with dialogues field.
    Returns dict: path_id -> [[text, translation, speaker], ...]"""
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
                if not text:
                    continue
                key = (text, speaker)
                if key not in seen:
                    seen.add(key)
                    entries.append([text, "", speaker])
    return by_pid


def extract_speakers(by_pid: dict) -> list:
    seen = OrderedDict()
    for entries in by_pid.values():
        for d in entries:
            sp = d[2] if len(d) > 2 else ""
            if sp and sp not in seen:
                seen[sp] = True
    return [[sp, "", ""] for sp in seen]


def extract_global_strings(summary_files: list) -> list:
    """Extract UI strings from settings_keys only (real display text from binary)."""
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
            keys.append([display, ""])
    return keys


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


def merge(existing: list, fresh: list, *key_idx: int) -> list:
    """Merge existing row data (translation, gender, etc.) into fresh entries.
    key_idx: indices that form the unique key (e.g. (0,2) for text+speaker).
    Non-key fields are preserved from existing when a match is found.
    """
    if not existing:
        return fresh
    old_map = {}
    for e in existing:
        k = tuple(e[i] for i in key_idx)
        old_map[k] = e
    merged = []
    for e in fresh:
        k = tuple(e[i] for i in key_idx)
        if k in old_map:
            old = old_map[k]
            new = list(e)
            for i in range(min(len(new), len(old))):
                if i not in key_idx:
                    new[i] = old[i]
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
        items = []
        for v in entry:
            v_str = str(v)
            v_str = v_str.replace("\\", "\\\\").replace('"', '\\"')
            v_str = "".join(c for c in v_str if c >= " " or c in "\n\r")
            items.append(f'"{v_str}"')
        lines.append("- [" + ", ".join(items) + "]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  -> {path} ({len(data)} entries)", file=sys.stderr)


def extract():
    print("Extractor: reading dump_assets/...", file=sys.stderr)

    chunks = find_chunks()
    summaries = find_summaries()
    print(f"  chunks: {len(chunks)}, summaries: {len(summaries)}", file=sys.stderr)

    by_pid = extract_dialogues(chunks)
    total = 0
    for pid in sorted(by_pid):
        fpath = OUT_DIR / f"dialogues.{pid}.yaml"
        existing = read_yaml(fpath)
        merged = merge(existing, by_pid[pid], 0, 2)
        total += len(merged)
        write_yaml(
            fpath,
            merged,
            header=f"Dialogues (path_id={pid}): [text, translation, speaker]",
        )

    fpath = OUT_DIR / "speakers.yaml"
    speakers = extract_speakers(by_pid)
    speakers = merge(read_yaml(fpath), speakers, 0)
    write_yaml(fpath, speakers, header="Speakers: [name, translation, gender]")

    fpath = OUT_DIR / "settings_keys.yaml"
    settings_keys = extract_global_strings(summaries)
    settings_keys = merge(read_yaml(fpath), settings_keys, 0)
    write_yaml(fpath, settings_keys, header="Settings keys: [key, translation]")

    print(f"\nDone: {total} dialogues across {len(by_pid)} sources, "
          f"{len(speakers)} speakers, {len(settings_keys)} settings keys",
          file=sys.stderr)


if __name__ == "__main__":
    extract()
