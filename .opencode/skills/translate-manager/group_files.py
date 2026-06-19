#!/usr/bin/env python3
"""Группировка файлов переводов в batch'и по числу непереведённых строк.

Usage:
    python .opencode/skills/translate-manager/group_files.py --files 1001.yaml 73203.yaml
    python .opencode/skills/translate-manager/group_files.py --max-lines 250
    python .opencode/skills/translate-manager/group_files.py --json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
DIALOGUES_DIR = PROJECT_DIR / "translations" / "dialogues"


def _parse_yaml_entries(raw: str) -> list[dict]:
    """Minimal YAML parser: list of dicts."""
    items = []
    current = {}
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            if current:
                items.append(current)
                current = {}
            continue
        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            rest = stripped[2:].strip()
            for key in ("text", "translation", "rich_translation", "speaker", "rich_text", "gender", "notes"):
                prefix = key + ":"
                if rest.startswith(prefix):
                    val = rest[len(prefix):].strip().strip("\"'")
                    current[key] = val
                    break
        elif current:
            for key in ("translation", "rich_translation", "speaker", "rich_text", "gender", "notes"):
                prefix = key + ":"
                if stripped.startswith(prefix):
                    val = stripped[len(prefix):].strip().strip("\"'")
                    current[key] = val
                    break
    if current:
        items.append(current)
    return items


def count_untranslated(path: Path) -> int:
    """Count untranslated entries in a YAML file.

    Entry is untranslated if:
    - translation is empty, OR
    - rich_text exists AND rich_translation is empty

    An "entry" is any dict with at least one of: text, rich_text
    """
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    entries = _parse_yaml_entries(raw)
    count = 0
    for entry in entries:
        txt = entry.get("text", "").strip()
        rich_text = entry.get("rich_text", "").strip()
        if not txt and not rich_text:
            continue
        tr = entry.get("translation", "").strip()
        rich_tr = entry.get("rich_translation", "").strip()
        if not tr:
            count += 1
        elif rich_text and not rich_tr:
            count += 1
    return count


def group_files(file_paths: list[Path], max_lines: int = 250) -> list[list[Path]]:
    """Разбить файлы на batch'и. Большие (>=max_lines) — по одному, мелкие — группами."""
    sizes = [(f, count_untranslated(f)) for f in file_paths]
    sizes.sort(key=lambda x: -x[1])

    big = []
    small = []
    for f, sz in sizes:
        if sz >= max_lines:
            big.append((f, sz))
        else:
            small.append((f, sz))

    batches = []
    for f, sz in big:
        batches.append([f])

    current_batch = []
    current_size = 0
    for f, sz in small:
        if current_size + sz > max_lines and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append(f)
        current_size += sz
    if current_batch:
        batches.append(current_batch)

    return batches


def write_batch_file(batches: list[list[Path]], max_lines: int, output_path: Path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_files = set()
    total_untranslated = 0
    flat = []
    for batch in batches:
        info = []
        batch_untranslated = 0
        for f in batch:
            untrans = count_untranslated(f)
            all_files.add(f.name)
            total_untranslated += untrans
            if untrans > 0:
                info.append({"name": f.name, "untranslated": untrans})
                batch_untranslated += untrans
        if info:
            flat.append({
                "file_count": len(info),
                "untranslated": batch_untranslated,
                "files": info,
            })

    lines = [f"created: {now}"]
    lines.append("params:")
    lines.append(f"  max_lines: {max_lines}")
    lines.append(f"total_files: {len(all_files)}")
    lines.append(f"total_untranslated: {total_untranslated}")
    lines.append("")
    lines.append("batches:")
    for i, b in enumerate(flat, 1):
        lines.append(f"  - id: {i}")
        lines.append(f"    untranslated: {b['untranslated']}")
        lines.append(f"    file_count: {b['file_count']}")
        lines.append("    files:")
        for f in b["files"]:
            lines.append(f"      - translations/dialogues/{f['name']}: {f['untranslated']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = sys.argv[1:]

    max_lines = 250
    file_names = []
    want_json = "--json" in args
    no_write = "--no-write" in args
    output_path = None

    i = 0
    while i < len(args):
        if args[i] == "--max-lines" and i + 1 < len(args):
            max_lines = int(args[i + 1])
            i += 2
        elif args[i] == "--files":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                file_names.append(args[i])
                i += 1
        elif args[i] == "--json":
            i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--no-write":
            i += 1
        else:
            file_names.append(args[i])
            i += 1

    if file_names:
        paths = [DIALOGUES_DIR / f for f in file_names]
    else:
        paths = sorted(DIALOGUES_DIR.glob("*.yaml"))

    existing = [p for p in paths if p.exists()]
    if not existing:
        print("Файлы не найдены", file=sys.stderr)
        sys.exit(1)

    batches = group_files(existing, max_lines)

    flat = []
    total_untranslated = 0
    for batch in batches:
        info = []
        batch_untranslated = 0
        for f in batch:
            untrans = count_untranslated(f)
            total_untranslated += untrans
            if untrans > 0:
                info.append({
                    "file": f.name,
                    "untranslated": untrans,
                })
                batch_untranslated += untrans
        if info:
            flat.append({
                "files": info,
                "untranslated": batch_untranslated,
                "file_count": len(info),
            })

    if want_json:
        output = {
            "total_files": len(set(p.name for p in existing)),
            "total_untranslated": total_untranslated,
            "batches": flat,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    if not no_write:
        if output_path is None:
            output_path = SKILL_DIR / "batch.yaml"
        write_batch_file(batches, max_lines, output_path)
        print(f"Batch file written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
