#!/usr/bin/env python3
"""Tests for group_files.py

Run: python .opencode/skills/translate-manager/group_files.test.py
"""

import json
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
import group_files as gf
from group_files import count_untranslated, group_files


def _make_yaml(path: Path, entries: list[str], translated: bool = False):
    """Write a YAML file with given text entries.

    If translated=True, fill translation field so entries count as translated.
    Default: translation="" → entries are untranslated.
    """
    lines = ["# Dialogues\n"]
    for t in entries:
        if translated:
            lines.append(f'- text: "{t}"\n  translation: "{t}-ru"\n')
        else:
            lines.append(f'- text: "{t}"\n  translation: ""\n')
    path.write_text("".join(lines), encoding="utf-8")


def test_count_untranslated_empty():
    p = Path(tempfile.mkdtemp()) / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert count_untranslated(p) == 0
    print("  PASS test_count_untranslated_empty")


def test_count_untranslated_comments_only():
    p = Path(tempfile.mkdtemp()) / "comments.yaml"
    p.write_text("# just\n# comments\n\n", encoding="utf-8")
    assert count_untranslated(p) == 0
    print("  PASS test_count_untranslated_comments_only")


def test_count_untranslated_all_untranslated():
    p = Path(tempfile.mkdtemp()) / "untranslated.yaml"
    p.write_text('- text: "A"\n  translation: ""\n\n- text: "B"\n  translation: ""\n', encoding="utf-8")
    assert count_untranslated(p) == 2
    print("  PASS test_count_untranslated_all_untranslated")


def test_count_untranslated_all_translated():
    p = Path(tempfile.mkdtemp()) / "translated.yaml"
    p.write_text('- text: "A"\n  translation: "A-ru"\n\n- text: "B"\n  translation: "B-ru"\n', encoding="utf-8")
    assert count_untranslated(p) == 0
    print("  PASS test_count_untranslated_all_translated")


def test_count_untranslated_rich_text_no_rich_translation():
    """rich_text есть, rich_translation пуст → считается непереведённым."""
    p = Path(tempfile.mkdtemp()) / "rich.yaml"
    p.write_text('- text: "A"\n  translation: "A-ru"\n  rich_text: "<b>A</b>"\n  rich_translation: ""\n', encoding="utf-8")
    assert count_untranslated(p) == 1
    print("  PASS test_count_untranslated_rich_text_no_rich_translation")


def test_count_untranslated_rich_text_filled():
    """rich_text и rich_translation оба заполнены → не непереведён."""
    p = Path(tempfile.mkdtemp()) / "rich_filled.yaml"
    p.write_text('- text: "A"\n  translation: "A-ru"\n  rich_text: "<b>A</b>"\n  rich_translation: "<b>A-ru</b>"\n', encoding="utf-8")
    assert count_untranslated(p) == 0
    print("  PASS test_count_untranslated_rich_text_filled")


def test_count_untranslated_no_text_field():
    """Записи без text поля не считаются."""
    p = Path(tempfile.mkdtemp()) / "notext.yaml"
    p.write_text('- speaker: "Zoey"\n  translation: ""\n', encoding="utf-8")
    assert count_untranslated(p) == 0
    print("  PASS test_count_untranslated_no_text_field")


def test_group_files_empty():
    assert group_files([]) == []
    print("  PASS test_group_files_empty")


def test_group_files_single_small():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "a.yaml", ["hello", "world"])
        batches = group_files([d / "a.yaml"], max_lines=50)
        assert len(batches) == 1
        assert len(batches[0]) == 1
    print("  PASS test_group_files_single_small")


def test_group_files_single_large():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "big.yaml", [f"s{i}" for i in range(100)])
        batches = group_files([d / "big.yaml"], max_lines=50)
        assert len(batches) == 1
        assert batches[0][0].name == "big.yaml"
    print("  PASS test_group_files_single_large")


def test_group_files_two_large():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "a.yaml", [f"a{i}" for i in range(60)])
        _make_yaml(d / "b.yaml", [f"b{i}" for i in range(60)])
        batches = group_files([d / "a.yaml", d / "b.yaml"], max_lines=50)
        assert len(batches) == 2
        assert len(batches[0]) == 1
        assert len(batches[1]) == 1
    print("  PASS test_group_files_two_large")


def test_group_files_merge_small():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "a.yaml", ["a1", "a2"])
        _make_yaml(d / "b.yaml", ["b1", "b2"])
        _make_yaml(d / "c.yaml", ["c1", "c2"])
        batches = group_files([d / "a.yaml", d / "b.yaml", d / "c.yaml"], max_lines=15)
        assert len(batches) == 1
        assert len(batches[0]) == 3
    print("  PASS test_group_files_merge_small")


def test_group_files_split_batches():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "a.yaml", ["a"] * 8)
        _make_yaml(d / "b.yaml", ["b"] * 8)
        _make_yaml(d / "c.yaml", ["c"] * 8)
        batches = group_files([d / "a.yaml", d / "b.yaml", d / "c.yaml"], max_lines=10)
        assert len(batches) == 3
        for b in batches:
            assert len(b) == 1
    print("  PASS test_group_files_split_batches")


def test_group_files_mixed():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "big.yaml", [f"b{i}" for i in range(30)])
        _make_yaml(d / "s1.yaml", ["s1"])
        _make_yaml(d / "s2.yaml", ["s2"])
        _make_yaml(d / "s3.yaml", ["s3"])
        batches = group_files([d / "big.yaml", d / "s1.yaml", d / "s2.yaml", d / "s3.yaml"], max_lines=20)
        assert len(batches) >= 2
        names = [b[0].name for b in batches if len(b) == 1]
        assert "big.yaml" in names
    print("  PASS test_group_files_mixed")


def test_group_exact_boundary():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _make_yaml(d / "a.yaml", ["a"] * 3)
        _make_yaml(d / "b.yaml", ["b"] * 3)
        batches = group_files([d / "a.yaml", d / "b.yaml"], max_lines=12)
        assert len(batches) == 1
        assert len(batches[0]) == 2
    print("  PASS test_group_exact_boundary")


def test_main_no_args():
    out = gf.main()
    assert out is None
    print("  PASS test_main_no_args")


def test_main_specific_files():
    args = ["--files", "5.yaml", "124.yaml"]
    save = sys.argv
    sys.argv = ["group_files.py"] + args
    try:
        gf.main()
    finally:
        sys.argv = save
    print("  PASS test_main_specific_files")


def test_main_json_output():
    args = ["--json"]
    save = sys.argv
    sys.argv = ["group_files.py"] + args
    try:
        gf.main()
    finally:
        sys.argv = save
    print("  PASS test_main_json_output")


def test_main_max_lines():
    args = ["--max-lines", "500", "--files", "5.yaml"]
    save = sys.argv
    sys.argv = ["group_files.py"] + args
    try:
        gf.main()
    finally:
        sys.argv = save
    print("  PASS test_main_max_lines")


def test_main_json_structure():
    """Verify --json produces valid JSON with expected fields."""
    import io
    save_stdout = sys.stdout
    save_argv = sys.argv
    sys.argv = ["group_files.py", "--json", "--files", "5.yaml", "124.yaml"]
    sys.stdout = io.StringIO()
    try:
        gf.main()
        output = sys.stdout.getvalue()
        data = json.loads(output)
        assert "total_files" in data
        assert "total_untranslated" in data
        assert "batches" in data
        assert isinstance(data["batches"], list)
    finally:
        sys.stdout = save_stdout
        sys.argv = save_argv
    print("  PASS test_main_json_structure")


if __name__ == "__main__":
    test_count_untranslated_empty()
    test_count_untranslated_comments_only()
    test_count_untranslated_all_untranslated()
    test_count_untranslated_all_translated()
    test_count_untranslated_rich_text_no_rich_translation()
    test_count_untranslated_rich_text_filled()
    test_count_untranslated_no_text_field()
    test_group_files_empty()
    test_group_files_single_small()
    test_group_files_single_large()
    test_group_files_two_large()
    test_group_files_merge_small()
    test_group_files_split_batches()
    test_group_files_mixed()
    test_group_exact_boundary()
    test_main_no_args()
    test_main_specific_files()
    test_main_json_output()
    test_main_max_lines()
    test_main_json_structure()
    print("\nAll 21 tests passed!")
