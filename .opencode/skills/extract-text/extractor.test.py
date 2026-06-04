#!/usr/bin/env python3
"""
Tests for extractor.py

Запуск: python .opencode/skills/extract-text/extractor.test.py
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

import extractor as ext


def setup_test_dump(out_dir: Path):
    dump = out_dir / "dump_assets"
    dump.mkdir(parents=True, exist_ok=True)

    summary = {
        "asset": "resources", "chunk": "summary", "total_objects": 10,
        "settings_keys": [
            {"key": "Settings.Fullscreen", "display": "Fullscreen"},
            {"key": "Settings.MusicVolume", "display": "Music Volume"},
            {"key": "Settings.FPSLimit", "display": "FPS Limit"},
        ],
        "global_strings": ["KF4wKTx", "Fullscreen"],
    }
    (dump / "resources.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary2 = {
        "asset": "level7", "chunk": "summary", "total_objects": 5,
        "settings_keys": [{"key": "Settings.lighting", "display": "\x00"}],
    }
    (dump / "level7.json").write_text(json.dumps(summary2, indent=2), encoding="utf-8")

    # Chunk with dialogues
    chunk = {
        "asset": "resources", "chunk": 14, "objects": [
            {"path_id": 73203, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "Zoey", "text": "Hello there!"},
                 {"speaker": "Sarah", "text": "Hi Zoey!"},
                 {"speaker": "Zoey", "text": "How are you?"},
                 {"speaker": "", "text": "Narration line"},
             ]},
            {"path_id": 73204, "type": "MonoBehaviour",
             "dialogues": [{"speaker": "Max", "text": "Hey!"}]},
        ],
    }
    (dump / "resources.chunk014.json").write_text(json.dumps(chunk, indent=2), encoding="utf-8")


def test_extract_dialogues():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        chunks = ext.find_chunks()
        assert len(chunks) == 1
        dialogues = ext.extract_dialogues(chunks)
        assert len(dialogues) == 5
        assert len(dialogues) == len(set((d["text"], d["speaker"]) for d in dialogues))
        assert all("translation" in d for d in dialogues)
        assert any(d["text"] == "Narration line" and d["speaker"] == "" for d in dialogues)
        print(f"  PASS: {len(dialogues)} dialogues")


def test_extract_speakers():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        speakers = ext.extract_speakers(ext.extract_dialogues(ext.find_chunks()))
        assert len(speakers) == 3
        names = {s["name"] for s in speakers}
        assert names == {"Zoey", "Sarah", "Max"}
        assert all("gender" in s and "translation" in s for s in speakers)
        print(f"  PASS: {len(speakers)} speakers")


def test_extract_global_strings():
    """Only settings_keys.display, no global_strings noise."""
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        strings = ext.extract_global_strings(ext.find_summaries())
        keys = {s["key"] for s in strings}
        assert keys == {"Fullscreen", "Music Volume", "FPS Limit"}
        assert "KF4wKTx" not in keys
        assert all("translation" in s for s in strings)
        print(f"  PASS: {len(strings)} strings — {sorted(keys)}")


def test_settings_keys_noise():
    """Only settings_keys.display, rejects null display."""
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "dump_assets"
        dump.mkdir()
        data = {
            "asset": "test", "chunk": "summary", "total_objects": 1,
            "settings_keys": [
                {"key": "Settings.Fullscreen", "display": "Fullscreen"},
                {"key": "Settings.lighting", "display": "\x00"},
            ],
        }
        (dump / "test.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        ext.DUMP_DIR = dump
        strings = ext.extract_global_strings(ext.find_summaries())
        assert len(strings) == 1
        assert strings[0]["key"] == "Fullscreen"
        print("  PASS: null display rejected")


def test_write_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.yaml"
        data = [{"key": "Fullscreen", "translation": ""}]
        ext.write_yaml(out, data, header="H")
        assert out.exists()
        c = out.read_text("utf-8")
        assert "# H" in c and 'key: "Fullscreen"' in c and 'translation: ""' in c
        print("  PASS: YAML written")


def test_empty_dump():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        assert len(ext.extract_dialogues([])) == 0
        assert len(ext.extract_speakers([])) == 0
        assert len(ext.extract_global_strings([])) == 0
        print("  PASS: empty dump")


def test_special_chars():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        chunk = {"asset": "r", "chunk": 0, "objects": [
            {"path_id": 1, "type": "MonoBehaviour",
             "dialogues": [
                 {"speaker": "Z", "text": 'with "quotes" and \\slash'},
                 {"speaker": "Z", "text": "with \x00null"},
             ]},
        ]}
        (ext.DUMP_DIR / "r.chunk000.json").write_text(json.dumps(chunk))
        out = Path(tmp) / "s.yaml"
        ext.write_yaml(out, ext.extract_dialogues(ext.find_chunks()))
        c = out.read_text("utf-8")
        assert '\\"' in c
        assert "\\\\" in c
        assert "\x00" not in c
        print("  PASS: special chars")


def test_no_duplicate_dialogues():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        for i in range(2):
            c = {"asset": "t", "chunk": i, "objects": [
                {"path_id": i, "type": "MonoBehaviour",
                 "dialogues": [{"speaker": "Z", "text": "Hi"}]},
            ]}
            (ext.DUMP_DIR / f"t.chunk{i:03d}.json").write_text(json.dumps(c))
        assert len(ext.extract_dialogues(ext.find_chunks())) == 1
        print("  PASS: dedup across chunks")


def test_real_dump_integrity():
    ext.DUMP_DIR = Path("dump_assets")
    ext.OUT_DIR = Path(tmp := tempfile.mkdtemp())
    ext.extract()
    assert (ext.OUT_DIR / "dialogues.yaml").exists()
    assert (ext.OUT_DIR / "speakers.yaml").exists()
    assert (ext.OUT_DIR / "settings_keys.yaml").exists()
    d = ext.extract_dialogues(ext.find_chunks())
    assert len(d) == 1544
    s = ext.extract_speakers(d)
    assert len(s) == 23
    g = ext.extract_global_strings(ext.find_summaries())
    assert len(g) >= 55, f"Expected >=55, got {len(g)}"
    assert all("translation" in x for x in d)
    assert all("translation" in x for x in s)
    assert all("translation" in x for x in g)
    print(f"  PASS: {len(d)} dialogues, {len(s)} speakers, {len(g)} strings")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [
        test_extract_dialogues,
        test_extract_speakers,
        test_extract_global_strings,
        test_settings_keys_noise,
        test_write_yaml,
        test_empty_dump,
        test_special_chars,
        test_no_duplicate_dialogues,
        test_real_dump_integrity,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  FAIL: {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
