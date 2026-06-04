#!/usr/bin/env python3
"""
extractor.py — Извлекает диалоги, UI-строки и имена персонажей из dump_assets/
и пишет YAML-файлы переводов.

Работает через dump_assets/ — не сканирует бинарники напрямую.

Файлы на выходе (в translations/):
  - dialogues.yaml:      диалоги         [text, speaker]
  - speakers.yaml:       персонажи       [name, gender]
  - global_strings.yaml: UI-строки       [key]
"""

import sys
import json
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


def extract_dialogues(chunk_files: list) -> list:
    """Scan all chunk files for objects with dialogues field."""
    dialogues = []
    seen = set()
    for fp in chunk_files:
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue
        for obj in data.get("objects", []):
            for d in obj.get("dialogues", []):
                text = d.get("text", "").strip()
                speaker = d.get("speaker", "").strip()
                if not text:
                    continue
                key = (text, speaker)
                if key not in seen:
                    seen.add(key)
                    dialogues.append({"text": text, "translation": "", "speaker": speaker})
    return dialogues


def extract_speakers(dialogues: list) -> list:
    seen = OrderedDict()
    for d in dialogues:
        sp = d["speaker"]
        if sp and sp not in seen:
            seen[sp] = True
    return [{"name": sp, "translation": "", "gender": ""} for sp in seen]


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
            keys.append({"key": display, "translation": ""})
    return keys


def write_yaml(path: Path, data: list, header: str = None):
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    if header:
        lines.append(f"# {header}")
        lines.append("")
    for entry in data:
        pairs = []
        for k, v in entry.items():
            v_str = str(v)
            v_str = v_str.replace("\\", "\\\\").replace('"', '\\"')
            v_str = "".join(c for c in v_str if c >= " " or c in "\n\r")
            pairs.append(f'{k}: "{v_str}"')
        lines.append("- {" + ", ".join(pairs) + "}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  -> {path} ({len(data)} entries)", file=sys.stderr)


def extract():
    print("Extractor: reading dump_assets/...", file=sys.stderr)

    chunks = find_chunks()
    summaries = find_summaries()
    print(f"  chunks: {len(chunks)}, summaries: {len(summaries)}", file=sys.stderr)

    # 1. Dialogues
    dialogues = extract_dialogues(chunks)
    write_yaml(
        OUT_DIR / "dialogues.yaml",
        dialogues,
        header="Dialogues: [text, translation, speaker]",
    )

    # 2. Speakers
    speakers = extract_speakers(dialogues)
    write_yaml(
        OUT_DIR / "speakers.yaml",
        speakers,
        header="Speakers: [name, translation, gender]",
    )

    # 3. Settings keys (Settings.* display keys only)
    settings_keys = extract_global_strings(summaries)
    write_yaml(
        OUT_DIR / "settings_keys.yaml",
        settings_keys,
        header="Settings keys: [key, translation]",
    )

    print(f"\nDone: {len(dialogues)} dialogues, {len(speakers)} speakers, "
          f"{len(settings_keys)} settings keys", file=sys.stderr)


if __name__ == "__main__":
    extract()
