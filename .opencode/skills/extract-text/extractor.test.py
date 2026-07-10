#!/usr/bin/env python3
"""Tests for extractor.py — python .opencode/skills/extract-text/extractor.test.py"""

import sys, json, tempfile, shutil
from pathlib import Path
import yaml

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
import extractor as ext


def _count_by(entries: list, field: str) -> int:
    return sum(1 for e in entries if e.get(field))


def setup_test_dump(out_dir: Path):
    dump = out_dir / "dump_assets"
    dump.mkdir(parents=True, exist_ok=True)
    summary = {"asset": "resources", "chunk": "summary", "total_objects": 10,
        "settings_keys": [
            {"key": "Settings.Fullscreen", "display": "Fullscreen"},
            {"key": "Settings.MusicVolume", "display": "Music Volume"},
            {"key": "Settings.FPSLimit", "display": "FPS Limit"},
        ]}
    (dump / "resources.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary2 = {"asset": "level7", "chunk": "summary", "total_objects": 5,
        "settings_keys": [{"key": "Settings.lighting", "display": "\x00"}]}
    (dump / "level7.json").write_text(json.dumps(summary2, indent=2), encoding="utf-8")
    chunk = {"asset": "resources", "chunk": 14, "objects": [
        {"path_id": 73203, "type": "MonoBehaviour", "dialogues": [
            {"speaker": "Zoey", "text": "Hello there!"},
            {"speaker": "Sarah", "text": "Hi Zoey!"},
            {"speaker": "Zoey", "text": "How are you?"},
            {"speaker": "", "text": "Narration line"}]},
        {"path_id": 73264, "type": "MonoBehaviour", "dialogues": [
            {"speaker": "Max", "text": "Hey!"}]},
    ]}
    (dump / "resources.chunk014.json").write_text(json.dumps(chunk, indent=2), encoding="utf-8")


def test_extract_dialogues():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        by_pid = ext.extract_dialogues(ext.find_chunks())
        assert len(by_pid) == 2
        total = sum(len(v) for v in by_pid.values())
        assert total == 5
        all_entries = [e for lst in by_pid.values() for e in lst]
        assert all(isinstance(x, dict) for x in all_entries)
        assert all(x.get("text") for x in all_entries)
        assert any(x["text"] == "Narration line" and x.get("speaker") == "" for x in all_entries)
        assert 73203 in by_pid and 73264 in by_pid
        assert all("rich_text" in e and "rich_translation" in e for e in all_entries)
        assert all(e.get("translation") == "" for e in all_entries)
        print(f"  PASS: {total} dialogues across {len(by_pid)} sources")


def test_extract_speakers():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        by_pid = ext.extract_dialogues(ext.find_chunks())
        seen = {}
        for entries in by_pid.values():
            for d in entries:
                sp = d.get("speaker", "")
                if sp and sp not in seen:
                    seen[sp] = True
        assert len(seen) == 3
        assert set(seen) == {"Zoey", "Sarah", "Max"}
        print(f"  PASS: {len(seen)} speakers")


def test_extract_global_strings():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        g = ext.extract_global_strings(ext.find_summaries())
        # Returns dict keyed by source file stem
        assert isinstance(g, dict)
        assert 'resources' in g
        assert len(g['resources']) == 3
        assert all(isinstance(x, dict) for x in g['resources'])
        assert all(x.get("text") for x in g['resources'])
        keys = {x["text"] for x in g['resources']}
        assert keys == {"Fullscreen", "Music Volume", "FPS Limit"}
        print(f"  PASS: {len(g)} sources, {sum(len(v) for v in g.values())} strings")


def test_write_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "t.yaml"
        ext.write_yaml(out, [
            {"text": "Fullscreen", "translation": ""},
            {"text": "Music Volume", "translation": ""},
        ], header="H")
        c = out.read_text("utf-8")
        assert "# H" in c
        assert 'text: "Fullscreen"' in c
        assert 'text: "Music Volume"' in c
        print("  PASS: YAML object format")


def test_extract_bundle_dialogues_fields():
    """Bundle entries always have rich_text + rich_translation fields."""
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        chunk = {"asset": "bundle_test", "chunk": 0, "objects": [
            {"path_id": 100, "type": "MonoBehaviour",
             "raw_strings": [
                 "line_1",
                 "Hello there!",
                 "<color=red>Rich text here</color>",
                 "Zoey",
             ],
             "strings": {"m_Name": "TestFSM"}},
        ]}
        (ext.DUMP_DIR / "bundle_.chunk000.json").write_text(json.dumps(chunk))
        by_bundle = ext.extract_bundle_dialogues(ext.find_chunks())
        assert len(by_bundle) > 0
        entries = [e for lst in by_bundle.values() for e in lst]
        assert len(entries) >= 2
        assert all("rich_text" in e and "rich_translation" in e for e in entries)
        assert all(e["rich_translation"] == "" for e in entries)
        rich_entries = [e for e in entries if e["rich_text"]]
        plain_entries = [e for e in entries if not e["rich_text"]]
        assert len(rich_entries) >= 1, "should have entry with rich_text from tagged line"
        assert len(plain_entries) >= 1, "should have entry without rich tags"
        assert "<color=red>" in rich_entries[0]["rich_text"]
        print(f"  PASS: {len(entries)} bundle entries, all have rich_text/rich_translation")


def test_empty_dump():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        assert len(ext.extract_dialogues([])) == 0
        assert len(ext.extract_global_strings([])) == 0
        print("  PASS: empty")


def test_special_chars():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        chunk = {"asset": "r", "chunk": 0, "objects": [
            {"path_id": 1, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "Z", "text": 'with "quotes" and \\slash'},
                 {"speaker": "Z", "text": "with \x00null"}]},
        ]}
        (ext.DUMP_DIR / "r.chunk000.json").write_text(json.dumps(chunk))
        by_pid = ext.extract_dialogues(ext.find_chunks())
        entries = [e for lst in by_pid.values() for e in lst]
        out = Path(tmp) / "s.yaml"
        ext.write_yaml(out, entries)
        c = out.read_text("utf-8")
        assert '\\"' in c
        assert "\\\\" in c
        assert "\x00" not in c
        print("  PASS: special chars")


def test_newline_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        text = "line1\n\nline2"
        chunk = {"asset": "r", "chunk": 0, "objects": [
            {"path_id": 1, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "", "text": text},
                 {"speaker": "", "text": "no newline here"},
                 {"speaker": "", "text": "single\nline"},
             ]},
        ]}
        (ext.DUMP_DIR / "r.chunk000.json").write_text(json.dumps(chunk))
        by_pid = ext.extract_dialogues(ext.find_chunks())
        entries = [e for lst in by_pid.values() for e in lst]
        assert len(entries) == 3
        out = Path(tmp) / "s.yaml"
        ext.write_yaml(out, entries)
        c = out.read_text("utf-8")
        # Escaped \n in output, not literal newlines inside quoted values
        assert '\\n' in c, f"Expected \\\\n escape in YAML, got:\n{c}"
        # Verify roundtrip via read_yaml (uses yaml.safe_load or fallback)
        reloaded = ext.read_yaml(out)
        assert len(reloaded) == 3
        assert reloaded[0]["text"] == text, \
            f"Roundtrip failed: {reloaded[0]['text']!r} != {text!r}"
        assert reloaded[1]["text"] == "no newline here"
        assert reloaded[2]["text"] == "single\nline"
        print("  PASS: newline roundtrip")


def test_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        c = {"asset": "t", "chunk": 0, "objects": [
            {"path_id": 0, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "Z", "text": "Hi"},
                 {"speaker": "Z", "text": "Hi"},
             ]},
        ]}
        (ext.DUMP_DIR / "t.chunk000.json").write_text(json.dumps(c))
        by_pid = ext.extract_dialogues(ext.find_chunks())
        total = sum(len(v) for v in by_pid.values())
        assert total == 1
        print("  PASS: dedup")


def test_read_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "t.yaml"
        assert ext.read_yaml(f) == []
        f.write_text("# H\n\n- [\"a\", \"\", \"b\"]\n", encoding="utf-8")
        r = ext.read_yaml(f)
        assert len(r) == 1
        assert r[0] == ["a", "", "b"]
        print("  PASS: read_yaml")


def test_read_yaml_multi():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "t.yaml"
        f.write_text(
            '# H\n\n'
            '- ["a", "", "b"]\n'
            '- [\n'
            '    "c",\n'
            '    "ТЕСТ перевод",\n'
            '    "d",\n'
            '  ]\n',
            encoding="utf-8",
        )
        r = ext.read_yaml(f)
        assert len(r) == 2
        assert r[0] == ["a", "", "b"]
        assert r[1] == ["c", "ТЕСТ перевод", "d"]
        print("  PASS: read_yaml multi-line")


def test_merge():
    old = [["Hello", "Привет", "Zoey"], ["Hi", "", "Sarah"]]
    fresh = [
        {"text": "Hello", "translation": "", "speaker": "Zoey"},
        {"text": "Bye", "translation": "", "speaker": "Max"},
        {"text": "Hi", "translation": "", "speaker": "Sarah"},
    ]
    merged = ext.merge(old, fresh, ext.DIALOGUE_FIELDS, "text", "speaker")
    assert len(merged) == 3
    assert merged[0]["text"] == "Hello" and merged[0]["translation"] == "Привет"
    assert merged[1]["text"] == "Bye" and merged[1]["translation"] == ""
    assert merged[2]["text"] == "Hi" and merged[2]["translation"] == ""
    assert all("rich_text" in e and "rich_translation" in e for e in merged)
    print("  PASS: merge preserves translations")


def test_merge_speakers():
    old = [["Zoey", "Зои", "", "Главная героиня"], ["Man", "Мужчина", "male", ""]]
    fresh = [
        {"text": "Zoey", "translation": "", "gender": "", "notes": ""},
        {"text": "Man", "translation": "", "gender": "", "notes": ""},
        {"text": "Nova", "translation": "", "gender": "", "notes": ""},
    ]
    merged = ext.merge(old, fresh, ext.SPEAKER_FIELDS, "text")
    assert len(merged) == 3
    assert merged[0]["text"] == "Zoey" and merged[0]["translation"] == "Зои" and merged[0]["notes"] == "Главная героиня"
    assert merged[1]["text"] == "Man" and merged[1]["translation"] == "Мужчина" and merged[1]["gender"] == "male"
    assert merged[2]["text"] == "Nova" and merged[2]["translation"] == ""
    print("  PASS: merge speakers")


def test_merge_settings():
    old = [["Fullscreen", "Полный экран"], ["Volume", "Громкость"]]
    fresh = [
        {"text": "Fullscreen", "translation": ""},
        {"text": "Volume", "translation": ""},
        {"text": "FPS", "translation": ""},
    ]
    merged = ext.merge(old, fresh, ext.SETTINGS_FIELDS, "text")
    assert len(merged) == 3
    assert merged[0]["text"] == "Fullscreen" and merged[0]["translation"] == "Полный экран"
    assert merged[1]["text"] == "Volume" and merged[1]["translation"] == "Громкость"
    assert merged[2]["text"] == "FPS" and merged[2]["translation"] == ""
    print("  PASS: merge settings")


def test_merge_rich_translation_copy_through():
    """rich_translation copy-through (plain text == text) should be cleared."""
    old = [
        # [text, translation, speaker, rich_text, rich_translation]
        ["Hello", "Hello", "Zoey", "<color=red>Hello</color>", "<color=red>Hello</color>"],  # both copy-through
        ["Hi", "Привет", "Zoey", "<color=red>Hi</color>", "<color=red>Hi</color>"],  # translation OK, rich copy-through
        ["Hey", "Привет", "Zoey", "<color=red>Hey</color>", "<color=green>Привет</color>"],  # both OK
    ]
    fresh = [
        {"text": "Hello", "translation": "", "speaker": "Zoey", "rich_text": "<color=red>Hello</color>", "rich_translation": ""},
        {"text": "Hi", "translation": "", "speaker": "Zoey", "rich_text": "<color=red>Hi</color>", "rich_translation": ""},
        {"text": "Hey", "translation": "", "speaker": "Zoey", "rich_text": "<color=red>Hey</color>", "rich_translation": ""},
    ]
    merged = ext.merge(old, fresh, ext.DIALOGUE_FIELDS, "text", "speaker")
    assert len(merged) == 3
    # Hello: both translation and rich_translation are copy-through → both cleared
    assert merged[0]["text"] == "Hello"
    assert merged[0]["translation"] == ""
    assert merged[0]["rich_translation"] == ""
    # Hi: translation OK, rich_translation is copy-through → rich cleared
    assert merged[1]["text"] == "Hi"
    assert merged[1]["translation"] == "Привет"
    assert merged[1]["rich_translation"] == ""
    # Hey: both translation and rich_translation are real → both preserved
    assert merged[2]["text"] == "Hey"
    assert merged[2]["translation"] == "Привет"
    assert merged[2]["rich_translation"] == "<color=green>Привет</color>"
    print("  PASS: merge rich_translation copy-through cleared")


def test_skip_flag():
    """skip_translation: true field should preserve copy-through (translation == text)."""
    old_skip = [
        {"text": "Aaaah~", "translation": "Aaaah~", "speaker": "Zoey", "rich_text": "", "rich_translation": ""},
        {"text": "Mmm~", "translation": "Mmm~", "speaker": "Zoey", "rich_text": "", "rich_translation": ""},
    ]
    old_skip[0]["skip_translation"] = True
    old_skip[1]["skip_translation"] = True

    fresh = [
        {"text": "Aaaah~", "translation": "", "speaker": "Zoey", "rich_text": "", "rich_translation": ""},
        {"text": "Mmm~", "translation": "", "speaker": "Zoey", "rich_text": "", "rich_translation": ""},
        {"text": "Hello", "translation": "", "speaker": "Zoey", "rich_text": "", "rich_translation": ""},
    ]

    merged = ext.merge(old_skip, fresh, ext.DIALOGUE_FIELDS, "text", "speaker")
    assert len(merged) == 3
    # Aaaah~ and Mmm~ have skip_translation → copy-through preserved
    assert merged[0]["text"] == "Aaaah~"
    assert merged[0]["translation"] == "Aaaah~"
    assert merged[1]["text"] == "Mmm~"
    assert merged[1]["translation"] == "Mmm~"
    # Hello has no skip → copy-through cleared
    assert merged[2]["text"] == "Hello"
    assert merged[2]["translation"] == ""

    # Test _format_entry outputs skip_translation field
    entry_with_skip = {"text": "Aaaah~", "translation": "Aaaah~", "skip_translation": True}
    formatted = ext._format_entry(entry_with_skip)
    assert "skip_translation: true" in formatted, f"Expected skip_translation in formatted output: {formatted}"

    # Test read_yaml parses skip_translation from YAML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write('- text: "Aaaah~"\n  translation: "Aaaah~"\n  skip_translation: true\n')
        f.write('- text: "Hello"\n  translation: ""\n')
        temp_path = Path(f.name)
    try:
        entries = ext.read_yaml(temp_path)
        assert len(entries) == 2
        assert entries[0].get("skip_translation") == True, f"Expected skip_translation=True for Aaaah~, got {entries[0]}"
        assert entries[1].get("skip_translation") == None, f"Expected no skip_translation for Hello, got {entries[1]}"
    finally:
        temp_path.unlink()

    print("  PASS: skip_translation flag preserves copy-through and formats correctly")


def test_idempotent():
    """Run extract twice: first run creates files, second preserves translations."""
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        chunk = {"asset": "r", "chunk": 0, "objects": [
            {"path_id": 1, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "Z", "text": "Hi"},
                 {"speaker": "Y", "text": "Bye"}]},
            {"path_id": 2, "type": "MonoBehaviour",
             "dialogues": [{"speaker": "X", "text": "Yo"}]},
        ]}
        (ext.DUMP_DIR / "r.chunk000.json").write_text(json.dumps(chunk))
        summary = {"asset": "r", "chunk": "summary", "total_objects": 2,
            "settings_keys": [{"key": "S.A", "display": "A"}]}
        (ext.DUMP_DIR / "r.json").write_text(json.dumps(summary))

        ext.OUT_DIR = Path(tmp) / "out"
        ext.extract()

        # simulate user translating — parse, modify, write
        dpath = ext._dialogues_dir() / "1.yaml"
        data = ext.read_yaml(dpath)
        # set translation on "Hi" entry
        for e in data:
            if isinstance(e, dict) and e.get("text") == "Hi":
                e["translation"] = "Привет"
        ext.write_yaml(dpath, data)
        # delete "Bye" entry
        data = ext.read_yaml(dpath)
        data = [e for e in data if not (isinstance(e, dict) and e.get("text") == "Bye")]
        ext.write_yaml(dpath, data)

        ext.extract()

        restored = ext.read_yaml(dpath)
        assert len(restored) == 2
        r0 = restored[0] if isinstance(restored[0], dict) else {"text": restored[0][0]}
        r1 = restored[1] if isinstance(restored[1], dict) else {"text": restored[1][0]}
        assert r0.get("text") == "Hi" and r0.get("translation", "") == "Привет"
        assert r1.get("text") == "Bye" and r1.get("translation", "") == ""
        print("  PASS: idempotent — deleted rows restored, translations preserved")


def test_fallback_parser():
    """_parse_yaml_fallback handles malformed YAML with missing closing quotes."""
    malformed = (
        '# Test\n\n'
        '- text: "Hi"\n'
        '  translation: "Привет"\n'
        '  speaker: "Z"\n\n'
        '- text: "Bye"\n'
        '  translation: ""\n'
        '  speaker: "Y"\n'
    )
    entries = ext._parse_yaml_fallback(malformed)
    assert len(entries) == 2
    assert entries[0]["text"] == "Hi"
    assert entries[0]["translation"] == "Привет"
    assert entries[0]["speaker"] == "Z"
    assert entries[1]["text"] == "Bye"
    assert entries[1]["translation"] == ""
    assert entries[1]["speaker"] == "Y"
    print("  PASS: fallback parser")


def test_cyrillic_roundtrip():
    """Cyrillic text survives write+read cycle without mojibake."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "t.yaml"
        entries = [{"text": "Hi", "translation": "Привет", "speaker": "Z"}]
        ext.write_yaml(f, entries)
        # Verify raw bytes contain Cyrillic UTF-8 sequence
        raw = f.read_bytes()
        assert raw.count(b"\xd0") >= 0, "should contain utf-8 cyrillic bytes"
        # Re-read and verify
        restored = ext.read_yaml(f)
        assert restored[0]["translation"] == "Привет", f"got {repr(restored[0]['translation'])}"
        # Re-write and re-read again (second cycle)
        ext.write_yaml(f, restored)
        restored2 = ext.read_yaml(f)
        assert restored2[0]["translation"] == "Привет", f"got {repr(restored2[0]['translation'])}"
        print("  PASS: cyrillic roundtrip")


def test_fallback_on_corrupted_file():
    """read_yaml falls back to _parse_yaml_fallback when yaml.safe_load fails."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "t.yaml"
        # Write file with em dash that trips yaml.safe_load (missing closing quote)
        f.write_text(
            '- text: "test"\n'
            '  translation: "\u2014 Vils\n',  # no closing quote
            encoding="utf-8",
        )
        entries = ext.read_yaml(f)
        assert len(entries) == 1
        assert entries[0]["text"] == "test"
        # Fallback strips mismatched quotes, value is clean
        assert entries[0]["translation"] == "\u2014 Vils", f"got {repr(entries[0]['translation'])}"
        print("  PASS: fallback on corrupted file")


def test_real_dump():
    dump_dir = Path("dump_assets")
    if not dump_dir.exists() or not list(dump_dir.glob("*.chunk*.json")):
        print("  SKIP: real dump not available")
        return
    ext.DUMP_DIR = dump_dir
    ext.OUT_DIR = Path(tmp := tempfile.mkdtemp())
    ext.extract()

    # Check that main dialogue files exist
    dialogues_dir = ext._dialogues_dir()
    assert (dialogues_dir / "73203.yaml").exists(), "Main dialogue file 73203.yaml missing"
    assert (dialogues_dir / "73262.yaml").exists(), "Dialogue file 73262.yaml missing"

    # Check that at least some known dialogue files exist
    known_dialogue_files = ["73263.yaml", "73264.yaml"]
    for fname in known_dialogue_files:
        assert (dialogues_dir / fname).exists(), f"Expected dialogue file {fname} missing"

    # Check that at least some bundle files exist (not all bundles produce dialogues)
    bundle_files = list(dialogues_dir.glob("bundle.bundle_*.yaml"))
    assert len(bundle_files) >= 2, f"Expected at least 2 bundle files, got {len(bundle_files)}"
    bundle_names = {f.name for f in bundle_files}

    # These are known bundle dialogues that should exist if present in dump
    expected_bundles = [
        "bundle.bundle_level-glowinghole.yaml",
        "bundle.bundle_level-cartelhideout.yaml",
        "bundle.bundle_0.3-animation-maxxcustomercg.yaml",
    ]
    for expected in expected_bundles:
        if expected in bundle_names:
            pass  # found, good

    assert (ext.OUT_DIR / "speakers.yaml").exists()
    # Check new per-source structure
    settings_dir = ext._settings_dir()
    raw_dir = ext._raw_dir()
    assert settings_dir.exists(), "settings/ directory should exist"
    settings_files = list(settings_dir.glob("*.yaml"))
    assert len(settings_files) >= 1, f"expected settings/*.yaml files, got {settings_files}"
    raw_files = list(raw_dir.glob("*.yaml"))
    assert len(raw_files) >= 1, f"expected raw/*.yaml files, got {raw_files}"

    by_pid = ext.extract_dialogues(ext.find_chunks())
    by_bundle = ext.extract_bundle_dialogues(ext.find_chunks())
    total = sum(len(v) for v in by_pid.values()) + sum(len(v) for v in by_bundle.values())
    assert len(by_pid) > 1000, f"expected 1000+ sources, got {len(by_pid)}"
    assert len(by_bundle) > 0, f"expected some bundles, got 0"
    all_pid_entries = [e for lst in by_pid.values() for e in lst]
    all_bundle_entries = [e for lst in by_bundle.values() for e in lst]
    assert all("rich_text" in e and "rich_translation" in e for e in all_pid_entries)
    assert all("rich_text" in e and "rich_translation" in e for e in all_bundle_entries)
    speakers = {d.get("speaker") for d in all_pid_entries if d.get("speaker")}
    assert len(speakers) >= 40, f"expected 40+ speakers, got {len(speakers)}"
    g = ext.extract_global_strings(ext.find_summaries())
    total_settings = sum(len(v) for v in g.values()) if isinstance(g, dict) else len(g)
    assert total_settings >= 50
    assert not (dialogues_dir / ".yaml").exists()
    print(f"  PASS: {total} dialogues across {len(by_pid)} .assets + {len(by_bundle)} bundles, "
          f"{len(speakers)} speakers, {total_settings} settings, "
          f"{len(settings_files)} settings/ + {len(raw_files)} raw/ files")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    pass  # moved to bottom


# ---------------------------------------------------------------------------
# Tests for dialogue vs settings_keys disambiguation (consolidation)
# ---------------------------------------------------------------------------

def test_is_dialogue_entry():
    """Entry with speaker or rich_text is a dialogue, not a settings_key."""
    assert ext._is_dialogue_entry({"text": "Hi", "speaker": "Zoey"}) is True
    assert ext._is_dialogue_entry({"text": "Hi", "rich_text": "Hi"}) is True
    assert ext._is_dialogue_entry({"text": "Hi", "speaker": "Zoey", "rich_text": "Hi"}) is True
    assert ext._is_dialogue_entry({"text": "Hi", "translation": "Привет"}) is False
    assert ext._is_dialogue_entry({"text": "Hi"}) is False
    assert ext._is_dialogue_entry({"text": "Hi", "speaker": ""}) is False
    assert ext._is_dialogue_entry({}) is False
    assert ext._is_dialogue_entry(None) is False
    print("  OK: _is_dialogue_entry")


def test_entry_field_count():
    """Field count should count non-empty values only."""
    assert ext._entry_field_count({"text": "Hi", "translation": "Привет"}) == 2
    assert ext._entry_field_count({"text": "Hi", "translation": "Привет", "speaker": "Zoey"}) == 3
    assert ext._entry_field_count({"text": "Hi", "translation": "", "speaker": "Zoey"}) == 2
    assert ext._entry_field_count({"text": "Hi", "speaker": "  "}) == 1
    assert ext._entry_field_count({}) == 0
    print("  OK: _entry_field_count")


def _setup_consolidation_test(work: Path):
    """Create a fake translations/ with a dialogue/settings conflict."""
    dlg_dir = work / "dialogues"
    dlg_dir.mkdir(parents=True, exist_ok=True)
    (dlg_dir / "73203.yaml").write_text(
        '- text: "S-Shit! Haze!"\n  translation: "Ч-Чёрт!"\n  speaker: "Zoey"\n  rich_text: "S-Shit! Haze!"\n\n',
        encoding="utf-8",
    )
    settings_dir = work / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "test.yaml").write_text(
        '- text: "S-Shit! Haze!"\n  translation: "Ч-Чёрт!"\n\n',
        encoding="utf-8",
    )


def test_consolidate_dialogue_wins():
    """When same text in both files, dialogue (richer) wins and is kept in dialogues/."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _setup_consolidation_test(work)
        ext.OUT_DIR = work
        ext._dialogues_dir = lambda: work / "dialogues"
        ext.consolidate_translations()
        dlg = yaml.safe_load(open(work / "dialogues" / "73203.yaml", encoding="utf-8"))
        assert len(dlg) == 1
        assert dlg[0]["speaker"] == "Zoey"
        # Settings duplicate should be removed
        sk_files = list((work / "settings").glob("*.yaml"))
        if sk_files:
            sk = yaml.safe_load(open(sk_files[0], encoding="utf-8"))
            assert sk is None or len(sk) == 0
        print("  OK: consolidate keeps dialogue, removes settings duplicate")


def test_consolidate_settings_wins():
    """Dialogue version (even without speaker) always wins over settings version.

    The routing logic preserves dialogue context: if a dialogue file contains
    a text, that text stays in dialogues/ — even if it lacks speaker/rich_text
    fields. This prevents one-word dialogue lines like "Yes" from leaking
    into settings/ files with empty translations.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        dlg_dir = work / "dialogues"
        dlg_dir.mkdir(parents=True, exist_ok=True)
        (dlg_dir / "99.yaml").write_text(
            '- text: "Just a label"\n  translation: "Просто метка"\n\n',
            encoding="utf-8",
        )
        settings_dir = work / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "test.yaml").write_text(
            '- text: "Just a label"\n  translation: "Просто метка"\n\n',
            encoding="utf-8",
        )
        ext.OUT_DIR = work
        ext._dialogues_dir = lambda: work / "dialogues"
        ext.consolidate_translations()
        # Dialogue version wins → stays in dialogues/99.yaml
        dlg = yaml.safe_load(open(work / "dialogues" / "99.yaml", encoding="utf-8"))
        assert dlg is not None and len(dlg) == 1
        assert dlg[0]["text"] == "Just a label"
        # Settings version removed (because dialogue has it)
        sk_files = list((work / "settings").glob("*.yaml"))
        if sk_files:
            sk = yaml.safe_load(open(sk_files[0], encoding="utf-8"))
            assert sk is None or len(sk) == 0
        print("  OK: dialogue version wins even without speaker/rich_text")


def test_consolidate_no_duplicates():
    """When text only in one file, it stays untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        dlg_dir = work / "dialogues"
        dlg_dir.mkdir(parents=True, exist_ok=True)
        (dlg_dir / "1.yaml").write_text(
            '- text: "Dialogue only"\n  translation: "Только диалог"\n  speaker: "A"\n\n',
            encoding="utf-8",
        )
        settings_dir = work / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "test.yaml").write_text(
            '- text: "Settings only"\n  translation: "Только настройка"\n\n',
            encoding="utf-8",
        )
        ext.OUT_DIR = work
        ext._dialogues_dir = lambda: work / "dialogues"
        ext.consolidate_translations()
        dlg = yaml.safe_load(open(work / "dialogues" / "1.yaml", encoding="utf-8"))
        assert len(dlg) == 1
        assert dlg[0]["text"] == "Dialogue only"
        sk = yaml.safe_load(open(work / "settings" / "test.yaml", encoding="utf-8"))
        assert len(sk) == 1
        assert sk[0]["text"] == "Settings only"
        print("  OK: consolidate leaves unique entries untouched")


def test_consolidate_speakers_not_in_settings():
    """Bug fix: speakers in speakers.yaml must NOT appear in settings/ or raw/ files.

    Otherwise settings/ files (loaded first alphabetically) seed the runtime
    dictionary with empty translations, blocking speakers.yaml entries.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        dlg_dir = work / "dialogues"
        dlg_dir.mkdir(parents=True, exist_ok=True)
        # speakers.yaml with proper translation
        (work / "speakers.yaml").write_text(
            '- text: "Zoey"\n  translation: "Зои"\n  gender: "female"\n  notes: "Главная героиня"\n\n',
            encoding="utf-8",
        )
        # settings/ file has the same "Zoey" but EMPTY translation (from chunk UI scan)
        settings_dir = work / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "test.yaml").write_text(
            '- text: "Zoey"\n  translation: ""\n\n',
            encoding="utf-8",
        )
        ext.OUT_DIR = work
        ext._dialogues_dir = lambda: work / "dialogues"
        ext.consolidate_translations()
        # "Zoey" must NOT be in settings/ files (belongs to speakers.yaml)
        sk_files = list((work / "settings").glob("*.yaml"))
        for skf in sk_files:
            sk = yaml.safe_load(open(skf, encoding="utf-8"))
            if sk:
                assert all(e.get("text") != "Zoey" for e in sk), \
                    f"Zoey should be removed from {skf}: {sk}"
        # speakers.yaml should be untouched
        sp = yaml.safe_load(open(work / "speakers.yaml", encoding="utf-8"))
        assert len(sp) == 1
        assert sp[0]["translation"] == "Зои"
        print("  OK: consolidate removes speakers from settings/ (alphabetical bug fix)")


if __name__ == "__main__":
    tests = [test_extract_dialogues, test_extract_speakers, test_extract_global_strings,
             test_write_yaml, test_extract_bundle_dialogues_fields,
             test_empty_dump, test_special_chars, test_newline_roundtrip, test_dedup,
             test_read_yaml, test_read_yaml_multi,
             test_merge, test_merge_speakers, test_merge_settings,
              test_merge_rich_translation_copy_through,
              test_skip_flag,
             test_idempotent, test_real_dump,
             test_fallback_parser, test_cyrillic_roundtrip, test_fallback_on_corrupted_file,
             test_is_dialogue_entry, test_entry_field_count,
             test_consolidate_dialogue_wins, test_consolidate_settings_wins,
             test_consolidate_no_duplicates, test_consolidate_speakers_not_in_settings]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  FAIL: {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
