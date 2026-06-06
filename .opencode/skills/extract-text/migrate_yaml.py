#!/usr/bin/env python3
"""
migrate_yaml.py — Конвертирует YAML из тупл-формата в объектный.

Запуск:
  python .opencode/skills/extract-text/migrate_yaml.py

Что делает:
  - Читает все .yaml из translations/
  - Конвертирует [a, b, c] → {text: a, translation: b, ...}
  - Пишет обратно в объектном формате
  - Оригиналы в translations.backup/

Схемы конвертации:
  dialogues.*.yaml:  [text, translation, speaker] → text, translation, speaker, rich_text, rich_translation
  speakers.yaml:     [name, translation, gender, notes] → text, translation, gender, notes
  settings_keys.yaml:[key, translation] → text, translation
"""

import sys
import json
from pathlib import Path

GAME_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights")
TRANSLATIONS = GAME_DIR / "translations"
BACKUP = GAME_DIR / "translations.backup"


def header_text(filepath: str) -> str:
    """Generate a header comment for the file based on its type."""
    name = filepath.name
    if name.startswith("dialogues."):
        if name == "dialogues.bundle.yaml":
            return "Dialogues (bundle/FSM)"
        pid = name.replace("dialogues.", "").replace(".yaml", "")
        return f"Dialogues (path_id={pid})"
    if name == "speakers.yaml":
        return "Speakers"
    if name == "settings_keys.yaml":
        return "Settings keys"
    return "Translations"


def schema_for(filepath: str) -> list:
    """Return list of field names for the given file."""
    name = filepath.name
    if name.startswith("dialogue"):
        return ["text", "translation", "speaker", "rich_text", "rich_translation"]
    if name == "speakers.yaml":
        return ["text", "translation", "gender", "notes"]
    if name == "settings_keys.yaml":
        return ["text", "translation"]
    return ["text", "translation"]


def convert_entry(tup: list, fields: list) -> dict:
    """Convert a tuple entry to a dict, padding missing fields with ''."""
    d = {}
    for i, f in enumerate(fields):
        d[f] = tup[i] if i < len(tup) else ""
    return d


def write_yaml(path: Path, data: list, fields: list):
    """Write entries as object-format YAML."""
    lines = []
    lines.append(f"# {header_text(path)}")
    lines.append("")
    for entry in data:
        lines.append("- " + _format_dict(entry, fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt(s: str) -> str:
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = "".join(c for c in s if c >= " " or c in "\n\r")
    return f'"{s}"'


def _format_dict(entry: dict, fields: list) -> str:
    """Format dict as YAML block entry. First field after '- ', rest indented."""
    first = fields[0]
    rest = [f for f in fields[1:] if entry.get(f)]
    parts = [f"{first}: {_fmt(entry.get(first, ''))}"]
    parts += [f"  {f}: {_fmt(entry.get(f, ''))}" for f in rest]
    return "\n".join(parts)


def read_raw_yaml(path: Path) -> list:
    """Read YAML file, return list of raw entries (lists or dicts)."""
    import yaml
    try:
        data = yaml.safe_load(path.read_text("utf-8"))
    except Exception as e:
        print(f"  ERROR reading {path.name}: {e}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        return []
    return data


def migrate_file(path: Path):
    """Convert a single YAML file from tuple to object format."""
    fields = schema_for(path)
    raw = read_raw_yaml(path)
    if not raw:
        print(f"  SKIP {path.name}: empty or unreadable", file=sys.stderr)
        return

    converted = []
    for entry in raw:
        if isinstance(entry, dict):
            # Already object format — just ensure all fields present
            d = {f: entry.get(f, "") for f in fields}
            converted.append(d)
        elif isinstance(entry, list):
            converted.append(convert_entry(entry, fields))
        else:
            print(f"  WARN {path.name}: unexpected entry type {type(entry).__name__}", file=sys.stderr)

    write_yaml(path, converted, fields)
    print(f"  OK {path.name}: {len(converted)} entries ({len(raw)} input)", file=sys.stderr)


def main():
    print("Migrating YAML: tuple → object format", file=sys.stderr)

    yaml_files = sorted(TRANSLATIONS.glob("*.yaml"))
    for fp in yaml_files:
        if fp.name == "test.yaml":
            continue
        migrate_file(fp)

    print("\nDone. Backups in translations.backup/", file=sys.stderr)


if __name__ == "__main__":
    main()
