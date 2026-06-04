#!/usr/bin/env python3
"""Tests for extractor.py — python .opencode/skills/extract-text/extractor.test.py"""

import sys, json, tempfile, shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
import extractor as ext


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
        assert len(by_pid) == 2  # two path_ids
        total = sum(len(v) for v in by_pid.values())
        assert total == 5
        all_entries = [e for lst in by_pid.values() for e in lst]
        assert all(isinstance(x, list) and len(x) == 3 for x in all_entries)
        assert any(x[0] == "Narration line" and x[2] == "" for x in all_entries)
        assert 73203 in by_pid and 73264 in by_pid
        print(f"  PASS: {total} dialogues across {len(by_pid)} sources")


def test_extract_speakers():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        s = ext.extract_speakers(ext.extract_dialogues(ext.find_chunks()))
        assert len(s) == 3
        assert all(isinstance(x, list) and len(x) == 3 for x in s)
        names = {x[0] for x in s}
        assert names == {"Zoey", "Sarah", "Max"}
        print(f"  PASS: {len(s)} speakers")


def test_extract_global_strings():
    with tempfile.TemporaryDirectory() as tmp:
        setup_test_dump(Path(tmp))
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        g = ext.extract_global_strings(ext.find_summaries())
        assert len(g) == 3
        assert all(isinstance(x, list) and len(x) == 2 for x in g)
        keys = {x[0] for x in g}
        assert keys == {"Fullscreen", "Music Volume", "FPS Limit"}
        print(f"  PASS: {len(g)} strings")


def test_write_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "t.yaml"
        ext.write_yaml(out, [["Fullscreen", ""], ["Music Volume", ""]], header="H")
        c = out.read_text("utf-8")
        assert '# H' in c
        assert '["Fullscreen", ""]' in c
        assert '["Music Volume", ""]' in c
        print("  PASS: YAML list format")


def test_empty_dump():
    with tempfile.TemporaryDirectory() as tmp:
        ext.DUMP_DIR = Path(tmp) / "dump_assets"
        ext.DUMP_DIR.mkdir()
        assert len(ext.extract_dialogues([])) == 0
        assert len(ext.extract_speakers({})) == 0
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
        assert total == 1  # dedup within same path_id
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
    fresh = [["Hello", "", "Zoey"], ["Bye", "", "Max"], ["Hi", "", "Sarah"]]
    merged = ext.merge(old, fresh, 0, 2)
    assert len(merged) == 3
    assert merged[0] == ["Hello", "Привет", "Zoey"]    # translation preserved
    assert merged[1] == ["Bye", "", "Max"]              # new entry, empty translation
    assert merged[2] == ["Hi", "", "Sarah"]             # no old translation, stays empty
    print("  PASS: merge preserves translations")


def test_merge_speakers():
    old = [["Zoey", "Зои", ""], ["Man", "Мужчина", "male"]]
    fresh = [["Zoey", "", ""], ["Man", "", ""], ["Nova", "", ""]]
    merged = ext.merge(old, fresh, 0)
    assert len(merged) == 3
    assert merged[0] == ["Zoey", "Зои", ""]
    assert merged[1] == ["Man", "Мужчина", "male"]
    assert merged[2] == ["Nova", "", ""]
    print("  PASS: merge speakers")


def test_merge_settings():
    old = [["Fullscreen", "Полный экран"], ["Volume", "Громкость"]]
    fresh = [["Fullscreen", ""], ["Volume", ""], ["FPS", ""]]
    merged = ext.merge(old, fresh, 0)
    assert len(merged) == 3
    assert merged[0] == ["Fullscreen", "Полный экран"]
    assert merged[1] == ["Volume", "Громкость"]
    assert merged[2] == ["FPS", ""]
    print("  PASS: merge settings")


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
        ext.extract()  # first run

        # simulate user translating some entries
        dpath = ext.OUT_DIR / "dialogues.1.yaml"
        dtext = dpath.read_text("utf-8")
        dtext = dtext.replace('"Hi", "", "Z"', '"Hi", "Привет", "Z"')
        dpath.write_text(dtext, encoding="utf-8")

        # simulate deleting a line
        lines = dpath.read_text("utf-8").splitlines()
        lines = [l for l in lines if "Bye" not in l]
        dpath.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ext.extract()  # second run — should restore "Bye" and keep "Привет"

        restored = ext.read_yaml(dpath)
        assert len(restored) == 2
        assert restored[0] == ["Hi", "Привет", "Z"]
        assert restored[1] == ["Bye", "", "Y"]
        print("  PASS: idempotent — deleted rows restored, translations preserved")


def test_real_dump():
    ext.DUMP_DIR = Path("dump_assets")
    ext.OUT_DIR = Path(tmp := tempfile.mkdtemp())
    ext.extract()
    # check per-path_id files
    assert (ext.OUT_DIR / "dialogues.73203.yaml").exists()
    assert (ext.OUT_DIR / "dialogues.73262.yaml").exists()
    assert (ext.OUT_DIR / "dialogues.73263.yaml").exists()
    assert (ext.OUT_DIR / "dialogues.73264.yaml").exists()
    assert (ext.OUT_DIR / "speakers.yaml").exists()
    assert (ext.OUT_DIR / "settings_keys.yaml").exists()
    # counts (no cross-dedup: each source counts separately)
    by_pid = ext.extract_dialogues(ext.find_chunks())
    total = sum(len(v) for v in by_pid.values())
    assert len(by_pid) == 4
    assert total == 1793
    s = ext.extract_speakers(by_pid)
    assert len(s) == 23
    g = ext.extract_global_strings(ext.find_summaries())
    assert len(g) == 55
    # no combined file
    assert not (ext.OUT_DIR / "dialogues.yaml").exists()
    print(f"  PASS: {total} dialogues across {len(by_pid)} sources, "
          f"{len(s)} speakers, {len(g)} keys")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [test_extract_dialogues, test_extract_speakers, test_extract_global_strings,
             test_write_yaml, test_empty_dump, test_special_chars, test_dedup,
             test_read_yaml, test_read_yaml_multi,
             test_merge, test_merge_speakers, test_merge_settings,
             test_idempotent, test_real_dump]
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
