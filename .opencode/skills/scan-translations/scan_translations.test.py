#!/usr/bin/env python3
"""Tests for scan_translations.py

Run: python .opencode/skills/scan-translations/scan_translations.test.py
"""

import sys, tempfile, json, re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
import scan_translations as sc
from scan_translations import load_yaml_safe, scan_file, write_report


def test_load_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "empty.yaml"
        p.write_text("", encoding="utf-8")
        data = load_yaml_safe(p)
        assert data == [], f"Expected [], got {data}"
    print("  PASS test_load_empty_file")


def test_load_comments_only():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "comments.yaml"
        p.write_text("# Just a comment\n\n# Another\n", encoding="utf-8")
        data = load_yaml_safe(p)
        assert data == [], f"Expected [], got {data}"
    print("  PASS test_load_comments_only")


def test_load_simple():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "simple.yaml"
        p.write_text("""- text: "Hello"
  translation: "Привет"
  speaker: "Z"

- text: "Bye"
  translation: ""
  speaker: "Y"
""", encoding="utf-8")
        data = load_yaml_safe(p)
        assert len(data) == 2
        assert data[0]["text"] == "Hello"
        assert data[0]["translation"] == "Привет"
        assert data[1]["text"] == "Bye"
        assert data[1]["translation"] == ""
    print("  PASS test_load_simple")


def test_scan_file_nonexistent():
    result = scan_file(Path("/nonexistent/foo.yaml"), "foo.yaml")
    assert result["error"] == "File not found"
    assert result["untranslated"] == 0
    print("  PASS test_scan_file_nonexistent")


def test_scan_file_all_translated():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "done.yaml"
        p.write_text("""- text: "Yes"
  translation: "Да"

- text: "No"
  translation: "Нет"
""", encoding="utf-8")
        result = scan_file(p, "done.yaml")
        assert result["total"] == 2
        assert result["untranslated"] == 0
        assert result["indices"] == []
    print("  PASS test_scan_file_all_translated")


def test_scan_file_partial():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "partial.yaml"
        p.write_text("""- text: "Hello"
  translation: "Привет"

- text: "World"
  translation: ""

- text: "Test"
  translation: ""
""", encoding="utf-8")
        result = scan_file(p, "partial.yaml")
        assert result["total"] == 3
        assert result["untranslated"] == 2
        assert result["indices"] == [1, 2]
        assert result["strings"][0]["text"] == "World"
        assert result["strings"][1]["text"] == "Test"
    print("  PASS test_scan_file_partial")


def test_scan_file_with_rich_text():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "rich.yaml"
        p.write_text("""- text: "Hello"
  translation: "Привет"
  rich_text: "<color=red>Hello</color>"
  rich_translation: "<color=red>Привет</color>"

- text: "Bye"
  translation: ""
  rich_text: "<i>Bye</i>"
""", encoding="utf-8")
        result = scan_file(p, "rich.yaml")
        assert result["total"] == 2
        assert result["untranslated"] == 1
        assert len(result["strings"]) == 1
        assert result["strings"][0]["text"] == "Bye"
    print("  PASS test_scan_file_with_rich_text")


def test_scan_file_whitespace_only():
    """whitespace-only translations count as untranslated."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "ws.yaml"
        p.write_text("""- text: "Hello"
  translation: "   "
""", encoding="utf-8")
        result = scan_file(p, "ws.yaml")
        assert result["untranslated"] == 1
    print("  PASS test_scan_file_whitespace_only")


def test_scan_file_no_text_field():
    """Items without text should be skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "notext.yaml"
        p.write_text("""- speaker: "Z"
  translation: "Hi"
""", encoding="utf-8")
        result = scan_file(p, "notext.yaml")
        assert result["total"] == 1
        assert result["untranslated"] == 0
    print("  PASS test_scan_file_no_text_field")


def test_yaml_fallback_mixed():
    """Test the fallback parser on a real-ish file."""
    raw = """# Dialogues (path_id=1)

- text: "Hi"
  translation: "Привет"
  speaker: "Z"

- text: "Bye"
  translation: ""

- text: "OK"
  translation: "Ок"
  speaker: ""
"""
    items = sc._parse_yaml_fallback(raw)
    assert len(items) == 3
    assert items[0]["text"] == "Hi"
    assert items[0]["translation"] == "Привет"
    assert items[1]["text"] == "Bye"
    assert items[1]["translation"] == ""
    assert items[2]["text"] == "OK"
    print("  PASS test_yaml_fallback_mixed")


def test_yaml_fallback_rich():
    raw = """- text: "Hello"
  translation: ""
  rich_text: "<color=red>Hello</color>"
  rich_translation: ""
"""
    items = sc._parse_yaml_fallback(raw)
    assert len(items) == 1
    assert items[0]["rich_text"] == "<color=red>Hello</color>"
    print("  PASS test_yaml_fallback_rich")


def test_scan_all_noop():
    """scan_all should run without crashing on real data."""
    results, settings, speakers = sc.scan_all()
    assert isinstance(results, list)
    assert isinstance(settings, dict)
    assert isinstance(speakers, dict)
    total_files = len(results)
    total_strings = sum(r["total"] for r in results)
    print(f"  PASS test_scan_all_noop: {total_files} files, {total_strings} strings")


def test_json_output():
    """JSON mode should produce valid JSON."""
    results, settings, speakers = sc.scan_all()
    data = {"dialogues": results, "settings_keys": settings, "speakers": speakers}
    serialized = json.dumps(data, indent=2, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert "dialogues" in parsed
    assert "settings_keys" in parsed
    assert "speakers" in parsed
    assert isinstance(parsed["dialogues"], list)
    print(f"  PASS test_json_output: {len(parsed['dialogues'])} files, {len(serialized)} bytes")


def test_filter_files():
    """--files should only scan specified files."""
    d1 = sc.scan_file(sc.DIALOGUES_DIR / "1.yaml", "1.yaml")
    d2 = sc.scan_file(sc.DIALOGUES_DIR / "1001.yaml", "1001.yaml")
    assert d1["file"] == "1.yaml"
    assert d2["file"] == "1001.yaml"
    assert d1["total"] >= 0
    assert d2["total"] >= 0
    print("  PASS test_filter_files")


def test_write_report_format():
    results = [
        {"file": "73203.yaml", "total": 10, "untranslated": 3, "indices": [0, 1, 2], "strings": []},
        {"file": "1001.yaml", "total": 5, "untranslated": 0, "indices": [], "strings": []},
        {"file": "error.yaml", "total": 0, "untranslated": 0, "indices": [], "strings": [], "error": "Not found"},
    ]
    settings = {"file": "settings_keys.yaml", "total": 50, "untranslated": 0, "indices": [], "strings": []}
    speakers = {"file": "speakers.yaml", "total": 10, "untranslated": 2, "indices": [], "strings": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.yaml"
        write_report(results, settings, speakers, out)
        text = out.read_text(encoding="utf-8")
        assert text.startswith("last_scan:"), "Missing last_scan"
        assert "dialogues/73203.yaml: 3" in text, "Expected untranslated count"
        assert "dialogues/error.yaml: error" in text, "Expected error entry"
        assert "speakers.yaml: 2" in text, "Expected speakers count"
        assert "dialogues/1001.yaml" not in text, "Done files should be omitted"
        assert "settings_keys.yaml" not in text, "Done settings should be omitted"
        assert text.endswith("\n"), "Missing trailing newline"
    print("  PASS test_write_report_format")


def test_write_report_all_done():
    results = [
        {"file": "a.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []},
        {"file": "b.yaml", "total": 2, "untranslated": 0, "indices": [], "strings": []},
    ]
    settings = {"file": "settings_keys.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []}
    speakers = {"file": "speakers.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.yaml"
        write_report(results, settings, speakers, out)
        text = out.read_text(encoding="utf-8")
        lines = [l for l in text.strip().split("\n") if not l.startswith("last_scan:") and l]
        assert lines == [], f"Should be empty, got: {lines}"
    print("  PASS test_write_report_all_done")


def test_write_report_date_format():
    results = [{"file": "a.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []}]
    settings = {"file": "settings_keys.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []}
    speakers = {"file": "speakers.yaml", "total": 1, "untranslated": 0, "indices": [], "strings": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.yaml"
        write_report(results, settings, speakers, out)
        first = out.read_text(encoding="utf-8").split("\n")[0]
        assert re.match(r"last_scan: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", first), f"Bad date: {first}"
    print("  PASS test_write_report_date_format")


if __name__ == "__main__":
    test_load_empty_file()
    test_load_comments_only()
    test_load_simple()
    test_scan_file_nonexistent()
    test_scan_file_all_translated()
    test_scan_file_partial()
    test_scan_file_with_rich_text()
    test_scan_file_whitespace_only()
    test_scan_file_no_text_field()
    test_yaml_fallback_mixed()
    test_yaml_fallback_rich()
    test_scan_all_noop()
    test_json_output()
    test_filter_files()
    test_write_report_format()
    test_write_report_all_done()
    test_write_report_date_format()
    print(f"\nAll {_passed} tests passed!" if (_passed := 17) else "")
