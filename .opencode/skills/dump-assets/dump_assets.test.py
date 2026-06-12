#!/usr/bin/env python3
"""
Tests for dump_assets.py

Run: python .opencode/skills/dump-assets/dump_assets.test.py
"""

import sys
import json
import os
import tempfile
from pathlib import Path

# Add script dir to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dump_assets import (
    discover_asset_files,
    scan_raw_strings,
    parse_dialogue_from_raw,
    _extract_json_string,
    pptr_to_dict,
    format_index_md,
    extract_object,
    DATA_DIR, GAME_DIR, OBJECTS_PER_CHUNK,
)

import UnityPy


# ============================================================
# Helpers
# ============================================================

def fake_pptr(file_id=0, path_id=123):
    """Create a minimal fake PPtr-like object."""
    class FakePPtr:
        m_FileID = file_id
        m_PathID = path_id
    return FakePPtr()


# ============================================================
# Tests: scan_raw_strings
# ============================================================

def test_scan_raw_strings_finds_ascii():
    data = b'hello\x00world\x00!!'
    result = scan_raw_strings(data)
    texts = [r['text'] for r in result]
    assert 'hello' in texts, f"Expected 'hello' in {texts}"
    assert 'world' in texts, f"Expected 'world' in {texts}"
    print("  PASS test_scan_raw_strings_finds_ascii")


def test_scan_raw_strings_skips_short():
    data = b'ab\x00xy\x00!!!!!'
    result = scan_raw_strings(data)
    for r in result:
        assert len(r['text']) >= 4, f"Short string found: {r['text']}"
    print("  PASS test_scan_raw_strings_skips_short")


def test_scan_raw_strings_requires_letters():
    data = b'1234\x00!!!!\x00abcd'
    result = scan_raw_strings(data)
    texts = [r['text'] for r in result]
    assert 'abcd' in texts, f"'abcd' should be found in {texts}"
    assert '1234' not in texts, f"'1234' has no letters, should be skipped"
    print("  PASS test_scan_raw_strings_requires_letters")


def test_scan_raw_strings_empty():
    data = b'\x00\x01\x02\xff'
    result = scan_raw_strings(data)
    assert len(result) == 0, f"Expected empty, got {len(result)}"
    print("  PASS test_scan_raw_strings_empty")


# ============================================================
# Tests: _extract_json_string
# ============================================================

def test_extract_json_simple():
    data = b'"hello" extra'
    val, end = _extract_json_string(data, 1)  # skip opening quote
    assert val == 'hello', f"Expected 'hello', got '{val}'"
    assert end == 7, f"Expected end=7, got {end}"
    print("  PASS test_extract_json_simple")


def test_extract_json_with_escapes():
    data = b'"hello \\"world\\" !" extra'
    val, end = _extract_json_string(data, 1)
    assert val == 'hello "world" !', f"Expected 'hello \"world\" !', got '{val}'"
    print("  PASS test_extract_json_with_escapes")


def test_extract_json_unicode():
    data = b'"hello\\u0021"'
    val, end = _extract_json_string(data, 1)
    assert val == 'hello!', f"Expected 'hello!', got '{val}'"
    print("  PASS test_extract_json_unicode")


def test_extract_json_empty():
    data = b'""'
    val, end = _extract_json_string(data, 1)
    assert val == '', f"Expected empty, got '{val}'"
    print("  PASS test_extract_json_empty")


# ============================================================
# Tests: parse_dialogue_from_raw
# ============================================================

def test_parse_dialogue_simple():
    raw = b'"Speaker":"Zoey","Text":"Hello there!"'
    result = parse_dialogue_from_raw(raw)
    assert len(result) == 1, f"Expected 1 dialogue, got {len(result)}"
    assert result[0]['speaker'] == 'Zoey'
    assert result[0]['text'] == 'Hello there!'
    print("  PASS test_parse_dialogue_simple")


def test_parse_dialogue_rich_text():
    raw = b'"Speaker":"Zoey","Text":"<color=red>Hello!</color>"'
    result = parse_dialogue_from_raw(raw)
    assert len(result) == 1
    assert result[0]['text'] == 'Hello!'
    assert 'rich_text' in result[0]
    print("  PASS test_parse_dialogue_rich_text")


def test_parse_dialogue_escaped_quotes():
    raw = b'"Speaker":"Zoey","Text":"<font=\\"FontName\\">It\'s cool</font>"'
    result = parse_dialogue_from_raw(raw)
    assert len(result) == 1, f"Expected 1 dialogue, got {len(result)}"
    assert result[0]['text'] == "It's cool"
    print("  PASS test_parse_dialogue_escaped_quotes")


def test_parse_dialogue_no_duplicates():
    raw = b'"Speaker":"Zoey","Text":"Hello""Speaker":"Zoey","Text":"Hello"'
    result = parse_dialogue_from_raw(raw)
    assert len(result) == 1, f"Expected dedup to 1, got {len(result)}"
    print("  PASS test_parse_dialogue_no_duplicates")


def test_parse_dialogue_empty():
    raw = b'some binary data without dialogue markers'
    result = parse_dialogue_from_raw(raw)
    assert len(result) == 0
    print("  PASS test_parse_dialogue_empty")


# ============================================================
# Tests: pptr_to_dict
# ============================================================

def test_pptr_to_dict():
    pptr = fake_pptr(0, 42)
    d = pptr_to_dict(pptr)
    assert d == {"file_id": 0, "path_id": 42}, f"Got {d}"
    print("  PASS test_pptr_to_dict")


def test_pptr_to_dict_invalid():
    d = pptr_to_dict("not a pptr")
    assert isinstance(d, str), f"Expected string fallback, got {type(d)}"
    print("  PASS test_pptr_to_dict_invalid")


# ============================================================
# Tests: discover_asset_files
# ============================================================

def test_discover_assets_count():
    files = discover_asset_files()
    assert len(files) >= 20, f"Expected >=20 files, got {len(files)}"
    names = [n for n, _ in files]
    # Common expected files
    expected = {'level0', 'resources'}
    for e in expected:
        assert e in names, f"Expected '{e}' in discovered files: {names}"
    print(f"  PASS test_discover_assets_count ({len(files)} files)")


def test_discover_assets_paths_exist():
    files = discover_asset_files()
    for name, fp in files:
        assert fp.exists(), f"Path does not exist: {fp}"
    print(f"  PASS test_discover_assets_paths_exist")


# ============================================================
# Tests: UnityPy integration
# ============================================================

def test_level0_loads():
    env = UnityPy.load(str(DATA_DIR / 'level0'))
    objs = list(env.objects)
    assert len(objs) > 0, "level0 should have objects"
    print(f"  PASS test_level0_loads ({len(objs)} objects)")


def test_level0_has_gameobjects():
    env = UnityPy.load(str(DATA_DIR / 'level0'))
    types = {obj.type.name for obj in env.objects}
    assert 'GameObject' in types, f"Expected GameObject in types: {types}"
    print(f"  PASS test_level0_has_gameobjects")


def test_level0_extract_object():
    env = UnityPy.load(str(DATA_DIR / 'level0'))
    objs = list(env.objects)
    extracted = extract_object(objs[0], env)
    assert 'path_id' in extracted, f"Missing path_id in {extracted}"
    assert 'type' in extracted, f"Missing type in {extracted}"
    print(f"  PASS test_level0_extract_object ({extracted['type']})")


def test_resources_has_dialogues():
    env = UnityPy.load(str(DATA_DIR / 'resources.assets'))
    total = 0
    for obj in env.objects:
        try:
            raw = obj.get_raw_data()
            dial = parse_dialogue_from_raw(raw)
            total += len(dial)
            if total > 100:
                break
        except Exception:
            pass
    assert total > 100, f"Expected >100 dialogues, got {total}"
    print(f"  PASS test_resources_has_dialogues ({total} found)")


def test_resources_object_types():
    env = UnityPy.load(str(DATA_DIR / 'resources.assets'))
    types = set()
    for obj in env.objects:
        types.add(obj.type.name)
    assert len(types) >= 10, f"Expected >=10 types, got {len(types)}: {types}"
    assert 'MonoBehaviour' in types, f"MonoBehaviour missing in: {types}"
    print(f"  PASS test_resources_object_types ({len(types)} types)")


# ============================================================
# Tests: format_index_md
# ============================================================

def test_format_index_md():
    results = [
        ('level0', 841, 1),
        ('resources', 100776, 22),
    ]
    md = format_index_md(results)
    assert 'level0' in md
    assert 'resources' in md
    assert 'level0.json' in md
    assert '841' in md
    assert '100776' in md
    print("  PASS test_format_index_md")


# ============================================================
# Run all
# ============================================================

def main():
    tests = [
        test_scan_raw_strings_finds_ascii,
        test_scan_raw_strings_skips_short,
        test_scan_raw_strings_requires_letters,
        test_scan_raw_strings_empty,
        test_extract_json_simple,
        test_extract_json_with_escapes,
        test_extract_json_unicode,
        test_extract_json_empty,
        test_parse_dialogue_simple,
        test_parse_dialogue_rich_text,
        test_parse_dialogue_escaped_quotes,
        test_parse_dialogue_no_duplicates,
        test_parse_dialogue_empty,
        test_pptr_to_dict,
        test_pptr_to_dict_invalid,
        test_discover_assets_count,
        test_discover_assets_paths_exist,
        test_level0_loads,
        test_level0_has_gameobjects,
        test_level0_extract_object,
        test_resources_has_dialogues,
        test_resources_object_types,
        test_format_index_md,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
