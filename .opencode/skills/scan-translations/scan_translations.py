#!/usr/bin/env python3
"""Scan translations/ and report untranslated strings.

Usage:
    python .opencode/skills/scan-translations/scan_translations.py
    python .opencode/skills/scan-translations/scan_translations.py --json
    python .opencode/skills/scan-translations/scan_translations.py --json --files 1001.yaml 73203.yaml
    python .opencode/skills/scan-translations/scan_translations.py --summary
"""

import json
import os
import sys
import glob
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
DIALOGUES_DIR = PROJECT_DIR / "translations" / "dialogues"
SETTINGS_PATH = PROJECT_DIR / "translations" / "settings_keys.yaml"
SPEAKERS_PATH = PROJECT_DIR / "translations" / "speakers.yaml"

HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass


def load_yaml_safe(path: Path) -> list | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if HAS_YAML:
        try:
            return yaml.safe_load(raw) or []
        except Exception:
            pass
    return _parse_yaml_fallback(raw)


def _parse_yaml_fallback(raw: str) -> list:
    """Minimal YAML parser for the subset we use: list of dicts with flat keys."""
    items = []
    current = {}
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            if current:
                items.append(current)
                current = {}
            continue
        if stripped.startswith("- text:"):
            if current:
                items.append(current)
            val = stripped[len("- text:"):].strip().strip("\"'")
            current = {"text": val, "translation": ""}
        elif current:
            for key in ("translation", "speaker", "rich_text", "rich_translation", "gender", "notes"):
                prefix = key + ":"
                if stripped.startswith(prefix):
                    val = stripped[len(prefix):].strip().strip("\"'")
                    current[key] = val
                    break
    if current:
        items.append(current)
    return items


def scan_file(path: Path, filename: str | None = None) -> dict:
    """Scan a single YAML file for untranslated strings.

    Returns:
        {
            "file": filename or path.name,
            "total": int,
            "untranslated": int,
            "indices": [int, ...],
            "strings": [{"index": int, "text": str, "speaker": str}, ...]
        }
    """
    data = load_yaml_safe(path)
    name = filename or path.name
    if data is None:
        return {"file": name, "error": "File not found", "total": 0, "untranslated": 0, "indices": [], "strings": []}
    if not isinstance(data, list):
        return {"file": name, "error": "Not a list", "total": 0, "untranslated": 0, "indices": [], "strings": []}

    result = {"file": name, "total": len(data), "untranslated": 0, "indices": [], "strings": []}
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        txt = item.get("text", "").strip()
        tr = item.get("translation", "").strip()
        if not txt:
            continue
        if not tr:
            result["untranslated"] += 1
            result["indices"].append(i)
            result["strings"].append({
                "index": i,
                "text": txt,
                "speaker": item.get("speaker", ""),
            })
    return result


def scan_all() -> list:
    files = sorted(glob.glob(str(DIALOGUES_DIR / "*.yaml")))
    results = [scan_file(Path(f)) for f in files]
    settings_result = scan_file(SETTINGS_PATH, "settings_keys.yaml")
    speakers_result = scan_file(SPEAKERS_PATH, "speakers.yaml")
    return results, settings_result, speakers_result


def print_summary(results, settings_result, speakers_result):
    total_files = len(results)
    fully_done = sum(1 for r in results if r["untranslated"] == 0 and "error" not in r)
    has_untranslated = [r for r in results if r["untranslated"] > 0]
    total_strings = sum(r["total"] for r in results if "error" not in r)
    total_untranslated = sum(r["untranslated"] for r in results if "error" not in r)

    print("translations/dialogues/")
    print(f"  Всего файлов: {total_files}")
    print(f"  Полностью переведено: {fully_done}")
    print(f"  Есть непереведённые: {len(has_untranslated)}")
    print(f"  Всего строк: {total_strings}")
    print(f"  Не переведено строк: {total_untranslated}")
    print()
    if has_untranslated:
        print("  Файлы с непереведёнными строками:")
        for r in sorted(has_untranslated, key=lambda x: -x["untranslated"])[:20]:
            pct = r["untranslated"] / r["total"] * 100
            print(f"    {r['file']:45s} — {r['untranslated']}/{r['total']} строк ({pct:.0f}%)")

    print()
    print(f"translations/settings_keys.yaml")
    print(f"  Всего строк: {settings_result['total']}", end="")
    if settings_result["untranslated"] > 0:
        print(f", не переведено: {settings_result['untranslated']}")
    else:
        print(" — OK")
    if settings_result.get("error"):
        print(f"  {settings_result['error']}")

    print()
    print(f"translations/speakers.yaml", end="")
    if speakers_result.get("error"):
        print(f"  {speakers_result['error']}")
    else:
        print(f" — {speakers_result['total']} speakers, {speakers_result['untranslated']} untranslated")


def print_json(results, settings_result, speakers_result):
    output = {
        "dialogues": results,
        "settings_keys": settings_result,
        "speakers": speakers_result,
    }
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def write_report(results, settings_result, speakers_result, output_path=None):
    if output_path is None:
        output_path = SKILL_DIR / "report.yaml"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"last_scan: {now}", ""]
    for r in sorted(results, key=lambda x: x["file"]):
        if "error" in r:
            lines.append(f"dialogues/{r['file']}: error")
        elif r["untranslated"] > 0:
            lines.append(f"dialogues/{r['file']}: {r['untranslated']}")
    if settings_result.get("error"):
        lines.append("settings_keys.yaml: error")
    elif settings_result["untranslated"] > 0:
        lines.append(f"settings_keys.yaml: {settings_result['untranslated']}")
    if speakers_result.get("error"):
        lines.append("speakers.yaml: error")
    elif speakers_result["untranslated"] > 0:
        lines.append(f"speakers.yaml: {speakers_result['untranslated']}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main():
    want_json = "--json" in sys.argv
    only_summary = "--summary" in sys.argv

    # Check if specific files requested
    file_list = None
    if "--files" in sys.argv:
        idx = sys.argv.index("--files")
        file_list = sys.argv[idx + 1:]

    if file_list:
        results = []
        for fn in file_list:
            path = DIALOGUES_DIR / fn
            results.append(scan_file(path, fn))
        settings_result = {"file": "settings_keys.yaml", "total": 0, "untranslated": 0, "indices": [], "strings": []}
        speakers_result = {"file": "speakers.yaml", "total": 0, "untranslated": 0, "indices": [], "strings": []}
        if "--settings" in sys.argv:
            settings_result = scan_file(SETTINGS_PATH, "settings_keys.yaml")
        if "--speakers" in sys.argv:
            speakers_result = scan_file(SPEAKERS_PATH, "speakers.yaml")
    else:
        results, settings_result, speakers_result = scan_all()

    report_path = write_report(results, settings_result, speakers_result)
    print(f"Report written to {report_path}")

    if want_json:
        print_json(results, settings_result, speakers_result)
    else:
        print_summary(results, settings_result, speakers_result)

    # Return exit code: 0 if nothing untranslated, 1 if there is
    total_unt = sum(r["untranslated"] for r in results) + settings_result["untranslated"]
    sys.exit(0 if total_unt == 0 else 1)


if __name__ == "__main__":
    main()
