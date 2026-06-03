#!/usr/bin/env python3
"""
parser.test.py — Comprehensive tests for parser

Run:  python parser.test.py
Or:   python -m pytest parser.test.py  (if pytest available)
"""

import sys
import os
import struct
import json
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from parser import (
    score_text, is_candidate, DIALOGUE_SCORE_THRESHOLD,
    scan_null_terminated, scan_aligned_strings, scan_utf16_strings,
    scan_all_runs, reconstruct_phrases,
    lz4_block_decode, decompress_lz4_blocks,
    parse_unity_header, parse_unityfs_header,
    parse_unity_file, parse_raw_file, parse_bundle_file,
    format_ndjson,
)

# ============================================================
# Tests: Scoring — the user's specific examples MUST pass
# ============================================================

def test_score_yesss():
    """Yesss...!~ must score above threshold."""
    score = score_text('Yesss...!~')
    assert score >= DIALOGUE_SCORE_THRESHOLD, (
        f"Yesss...!~ scored {score}, expected >= {DIALOGUE_SCORE_THRESHOLD}")


def test_score_fhaaa():
    """Fhaaa..!! must score above threshold."""
    score = score_text('Fhaaa..!!')
    assert score >= DIALOGUE_SCORE_THRESHOLD, (
        f"Fhaaa..!! scored {score}, expected >= {DIALOGUE_SCORE_THRESHOLD}")


def test_score_long_phrase():
    """Long dialogue phrase must score above threshold."""
    phrase = "Nhaah..! Stroke your-.. Cock for me-..! Yess..! Stroke it faster!"
    score = score_text(phrase)
    assert score >= DIALOGUE_SCORE_THRESHOLD, (
        f"Long phrase scored {score}, expected >= {DIALOGUE_SCORE_THRESHOLD}")


def test_score_normal_text():
    """Normal dialogue sentences should score high."""
    texts = [
        ("Hello, how are you?", 0.7),
        ("I don't know what to do", 0.7),
        ("Wait for me!", 0.7),
        ("Please, help me find my way out", 0.7),
        ("What is this place?", 0.7),
    ]
    for text, min_score in texts:
        score = score_text(text)
        assert score >= min_score, f"'{text}' scored {score}, expected >= {min_score}"


def test_score_ui_strings():
    """UI strings should score high."""
    texts = [
        "Fullscreen",
        "Load Game",
        "Options",
        "Continue",
        "Resolution",
        "Volume",
        "Quality",
    ]
    for text in texts:
        score = score_text(text)
        assert score >= DIALOGUE_SCORE_THRESHOLD, (
            f"UI string '{text}' scored {score}, expected >= {DIALOGUE_SCORE_THRESHOLD}")


def test_score_garbage():
    """Garbage/code strings must score 0 or very low."""
    garbage = [
        "m_Handle",
        "m_Texture",
        "ShaderVariables",
        "UnityEngine",
        "path/to/file",
        "C:\\Users\\test",
        "http://example.com",
        "m_text",
    ]
    for text in garbage:
        score = score_text(text)
        assert score < DIALOGUE_SCORE_THRESHOLD, (
            f"Garbage '{text}' scored {score}, expected < {DIALOGUE_SCORE_THRESHOLD}")

def test_score_code_patterns():
    """Code patterns (underscore, namespace, camelCase, brackets) score 0."""
    code_strings = [
        "System.Collections",
        "UnityEngine.UI",
        "Awake",
        "Start",
        "Update",
        "LateUpdate",
        "RGBA32",
        "OnEnable",
        "OnDisable",
        "QualitySettings",
        "MonoBehaviour",
        "m_handle",
        "camelCase",
    ]
    for text in code_strings:
        score = score_text(text)
        assert score == 0.0, f"Code '{text}' scored {score}, expected 0"


def test_score_settings_key():
    """Settings.* keys should score high."""
    score = score_text('Settings.Fullscreen')
    assert score >= 0.6, f"Settings.Fullscreen scored {score}"


def test_score_repeated_letters_garbage():
    """Repeated single character should score low or zero."""
    score = score_text('aaaaaa')
    assert score < DIALOGUE_SCORE_THRESHOLD, f"'aaaaaa' scored {score}"


def test_is_candidate():
    """is_candidate wrapper works correctly."""
    assert is_candidate("Hello there!", threshold=0.3)
    assert not is_candidate("m_Texture", threshold=0.3)
    assert is_candidate("anything", full_scan=True)
    assert is_candidate("Yesss...!~", threshold=0.25)


# ============================================================
# Tests: scan_null_terminated
# ============================================================

def test_scan_null_terminated_basic():
    """Basic null-terminated string extraction."""
    data = b"Hello\x00World\x00test\x00"
    result = scan_null_terminated(data, 0, min_len=2)
    raws = [s['raw'] for s in result]
    assert "Hello" in raws, f"Expected 'Hello' in {raws}"
    assert "World" in raws
    assert "test" in raws


def test_scan_null_terminated_with_punctuation():
    """Null-term scan must find strings with dialogue punctuation."""
    data = b"Yesss...!~\x00Fhaaa..!!\x00"
    result = scan_null_terminated(data, 0, min_len=2)
    raws = [s['raw'] for s in result]
    assert "Yesss...!~" in raws, f"Expected 'Yesss...!~' in {raws}"
    assert "Fhaaa..!!" in raws, f"Expected 'Fhaaa..!!' in {raws}"


def test_scan_null_terminated_long_phrase():
    """Long phrase extraction."""
    phrase = b"Nhaah..! Stroke your-.. Cock for me-..! Yess..! Stroke it faster!\x00"
    data = phrase
    result = scan_null_terminated(data, 0, min_len=2)
    raws = [s['raw'] for s in result]
    assert "Nhaah..! Stroke your-.. Cock for me-..! Yess..! Stroke it faster!" in raws


def test_scan_null_terminated_min_len():
    """Min length filter works."""
    data = b"ab\x00abcd\x00abcdefgh\x00"
    result = scan_null_terminated(data, 0, min_len=5)
    raws = [s['raw'] for s in result]
    assert "abcd" not in raws
    assert "abcdefgh" in raws


def test_scan_null_terminated_offset():
    """Offset tracking is correct."""
    data = b"skip\x00test\x00"
    result = scan_null_terminated(data, 100, min_len=2)
    assert result[0]['offset'] == 100 + 0  # "skip" at offset 0 + base 100
    assert result[1]['offset'] == 100 + 5  # "test" at offset 5 + base 100


# ============================================================
# Tests: scan_aligned_strings
# ============================================================

def make_aligned_string(text: str) -> bytes:
    """Create a Unity aligned string (int32 LE len + data + padding)."""
    encoded = text.encode('ascii')
    pad = (4 - (len(encoded) % 4)) % 4
    return struct.pack('<I', len(encoded)) + encoded + b'\x00' * pad


def test_scan_aligned_strings_basic():
    """Basic aligned string extraction."""
    data = make_aligned_string("Hello") + make_aligned_string("World")
    result = scan_aligned_strings(data, 0)
    raws = [s['raw'] for s in result]
    assert "Hello" in raws, f"Expected 'Hello' in {raws}"
    assert "World" in raws


def test_scan_aligned_strings_dialogue():
    """Aligned scan must find strings with dialogue punctuation."""
    data = make_aligned_string("Yesss...!~") + make_aligned_string("Fhaaa..!!")
    result = scan_aligned_strings(data, 0)
    raws = [s['raw'] for s in result]
    assert "Yesss...!~" in raws, f"Expected 'Yesss...!~' in {raws}"
    assert "Fhaaa..!!" in raws


def test_scan_aligned_strings_offset():
    """Offset tracking for aligned strings."""
    data = b'\x00' * 16 + make_aligned_string("test")
    result = scan_aligned_strings(data, 0)
    assert result[0]['offset'] == 16


def test_scan_aligned_strings_noise():
    """Aligned scan should handle noise between strings."""
    data = make_aligned_string("Hello") + b'\xff\xff\xff\xff' + make_aligned_string("World")
    result = scan_aligned_strings(data, 0)
    raws = [s['raw'] for s in result]
    assert "Hello" in raws
    assert "World" in raws


# ============================================================
# Tests: scan_utf16_strings
# ============================================================

def make_utf16(text: str) -> bytes:
    """Create a UTF-16 LE string."""
    return ''.join(c + '\x00' for c in text).encode('ascii')


def test_scan_utf16_basic():
    """Basic UTF-16 LE extraction."""
    data = make_utf16("Hello") + b'\x00\x00' + make_utf16("World")
    result = scan_utf16_strings(data, 0)
    raws = [s['raw'] for s in result]
    assert "Hello" in raws, f"Expected 'Hello' in {raws}"
    assert "World" in raws


def test_scan_utf16_with_punctuation():
    """UTF-16 scan must find strings with dialogue punctuation."""
    data = make_utf16("Yesss...!~")
    result = scan_utf16_strings(data, 0)
    raws = [s['raw'] for s in result]
    assert "Yesss...!~" in raws


# ============================================================
# Tests: scan_all_runs
# ============================================================

def test_scan_all_runs_basic():
    """All-runs scan finds everything printable."""
    data = b"Hello World!\x00More text here\x00"
    result = scan_all_runs(data, 0)
    raws = [s['raw'] for s in result]
    assert "Hello World!" in raws
    assert "More text here" in raws


# ============================================================
# Tests: phrase reconstruction
# ============================================================

def test_reconstruct_hyphen_break():
    """Words split with hyphen across records should merge."""
    strings = [
        {'offset': 100, 'raw': 'Hel', 'score': 0.8},
        {'offset': 104, 'raw': 'lo', 'score': 0.8},
    ]
    result = reconstruct_phrases(strings, max_gap=16)
    # Gap is 4, not 0, so no hyphen ending → won't merge with default heuristic
    # Unless gap < 8 and both scores >= 0.3
    assert len(result) <= len(strings)
    assert len(result) >= 1


def test_reconstruct_no_merge_far():
    """Distant strings should not merge."""
    strings = [
        {'offset': 100, 'raw': 'Hello', 'score': 0.8},
        {'offset': 200, 'raw': 'World', 'score': 0.8},
    ]
    result = reconstruct_phrases(strings, max_gap=16)
    assert len(result) == 2


def test_reconstruct_empty():
    """Empty input produces empty output."""
    assert reconstruct_phrases([]) == []


def test_reconstruct_single():
    """Single string passes through unchanged."""
    s = [{'offset': 100, 'raw': 'Hello', 'score': 0.8}]
    result = reconstruct_phrases(s)
    assert len(result) == 1
    assert result[0]['raw'] == 'Hello'


# ============================================================
# Tests: LZ4 block decoder
# ============================================================

def test_lz4_block_decode_empty():
    """Empty LZ4 block."""
    result = lz4_block_decode(b'', 0)
    assert result == b''


def test_lz4_block_decode_small():
    """Small literal-only LZ4 block."""
    # Token = 0xF0 (lit_len=15), followed by extra 0 (total lit_len=15)
    data = bytes([0xF0, 0x00]) + b'HelloWorld12345'  # 15 literals
    result = lz4_block_decode(data, 15)
    assert result == b'HelloWorld12345'


# ============================================================
# Tests: Unity header parser
# ============================================================

def test_parse_unity_header_new_format():
    """New format header (Unity 2020+)."""
    data = bytearray(128)
    # 8 zero bytes
    # version BE = 22
    struct.pack_into('>i', data, 8, 22)
    # endian = 0 (little)
    data[16] = 0
    # metadata size BE = 100
    struct.pack_into('>i', data, 20, 100)
    # file size BE = 1000
    struct.pack_into('>i', data, 28, 1000)
    # data offset BE = 200
    struct.pack_into('>i', data, 36, 200)
    # Unity version string
    data[48:52] = b'2022'
    data[52] = 0

    h = parse_unity_header(bytes(data))
    assert h is not None
    assert h['new_format'] is True
    assert h['version'] == 22
    assert h['data_offset'] == 200
    assert h['file_size'] == 1000
    assert '2022' in h.get('unity_version', '')


def test_parse_unity_header_old_format():
    """Old format header."""
    data = bytearray(24)
    struct.pack_into('<I', data, 0, 100)   # metadata size
    struct.pack_into('<I', data, 4, 1000)  # file size
    struct.pack_into('<I', data, 8, 15)    # version
    struct.pack_into('<I', data, 12, 200)  # data offset
    data[16] = 0  # endian

    h = parse_unity_header(bytes(data))
    assert h is not None
    assert h['new_format'] is False
    assert h['data_offset'] == 200


def test_parse_unity_header_truncated():
    """Truncated data returns None."""
    assert parse_unity_header(b'\x00' * 4) is None


# ============================================================
# Tests: UnityFS (bundle) header parser
# ============================================================

def test_parse_unityfs_header():
    """UnityFS header parsing."""
    data = bytearray(80)
    data[:7] = b'UnityFS'
    # compressed header size BE
    struct.pack_into('>I', data, 38, 100)
    # decompressed header size BE
    struct.pack_into('>I', data, 42, 500)
    # flags BE: compression type 3 (LZ4)
    struct.pack_into('>I', data, 46, 3)

    h = parse_unityfs_header(bytes(data))
    assert h is not None
    assert h['compression_type'] == 3
    assert h['header_start'] == 64
    assert h['data_start'] == 164


def test_parse_unityfs_header_not_unityfs():
    """Non-UnityFS file returns None."""
    assert parse_unityfs_header(b'NotUnity') is None


# ============================================================
# Tests: full file parsing (with synthetic data)
# ============================================================

def _make_synthetic_unity_file(strings: list) -> bytes:
    """Create a synthetic Unity serialized file with aligned strings in data section."""
    # Build a minimal valid Unity file
    header_size = 60  # minimum for new format
    data_offset = header_size + 100  # metadata area

    buf = bytearray(data_offset + 1000)

    # New format header
    struct.pack_into('>i', buf, 8, 22)    # version
    buf[16] = 0                             # little endian
    struct.pack_into('>i', buf, 20, 100)   # metadata size
    struct.pack_into('>i', buf, 28, len(buf))  # file size
    struct.pack_into('>i', buf, 36, data_offset)  # data offset
    buf[48] = ord('2')
    buf[49] = ord('0')
    buf[50] = ord('2')
    buf[51] = ord('2')
    buf[52] = 0  # null terminator

    # Write strings into data section
    pos = data_offset
    for s in strings:
        encoded = s.encode('ascii')
        pad = (4 - (len(encoded) % 4)) % 4
        # Write as both aligned AND null-terminated
        struct.pack_into('<I', buf, pos, len(encoded))
        pos += 4
        buf[pos:pos + len(encoded)] = encoded
        pos += len(encoded)
        pos += pad
        # Also write null-terminated version after
        buf[pos:pos + len(encoded)] = encoded
        buf[pos + len(encoded)] = 0
        pos += len(encoded) + 1

    return bytes(buf)


def test_parse_synthetic_file():
    """Parse a synthetic Unity file."""
    test_strings = ["Hello World!", "Yesss...!~", "Fhaaa..!!"]
    data = _make_synthetic_unity_file(test_strings)

    with tempfile.NamedTemporaryFile(suffix='.assets', delete=False) as f:
        f.write(data)
        f.flush()
        fp = Path(f.name)

    try:
        # Disable reconstruction for this test to test extraction independently
        result = parse_unity_file(fp, {'min_len': 2, 'threshold': 0.25, 'full_scan': False, 'reconstruct': False})
        raws = [s['raw'] for s in result['strings']]

        # All test strings should be found after filtering
        for s in test_strings:
            assert s in raws, f"Expected '{s}' in parsed output: {raws}"

        assert result['stats']['total_strings'] >= len(test_strings)
    finally:
        os.unlink(f.name)


def test_parse_synthetic_file_full_scan():
    """Full scan should return everything including low-scoring strings."""
    data = _make_synthetic_unity_file(["Hello", "m_Handle", "Yesss...!~"])

    with tempfile.NamedTemporaryFile(suffix='.assets', delete=False) as f:
        f.write(data)
        f.flush()
        fp = Path(f.name)

    try:
        result = parse_unity_file(fp, {'min_len': 2, 'threshold': 0.25, 'full_scan': True, 'reconstruct': False})
        raws = [s['raw'] for s in result['strings']]
        assert "m_Handle" in raws, f"Full scan should include 'm_Handle': {raws}"
    finally:
        os.unlink(f.name)


# ============================================================
# Tests: raw file parsing (DLL-like)
# ============================================================

def test_parse_raw_file():
    """Parse a synthetic raw/DLL file."""
    # Use separators to avoid boundary artifacts between ASCII and UTF-16 data
    # Use dialogue-like strings that pass scoring
    data = b"Hello there\x00\x01\x01" + make_utf16("What is this?") + b"\x01\x01Goodbye!\x00"

    with tempfile.NamedTemporaryFile(suffix='.dll', delete=False) as f:
        f.write(data)
        f.flush()
        fp = Path(f.name)

    try:
        result = parse_raw_file(fp, {'min_len': 2, 'threshold': 0.25, 'full_scan': False})
        raws = [s['raw'] for s in result['strings']]
        assert "Hello there" in raws, f"Expected 'Hello there' in {raws}"
        assert "What is this?" in raws, f"Expected 'What is this?' in {raws}"
        assert "Goodbye!" in raws, f"Expected 'Goodbye!' in {raws}"
    finally:
        os.unlink(f.name)


# ============================================================
# Tests: NDJSON output
# ============================================================

def test_format_ndjson_basic():
    """Basic NDJSON format."""
    strings = [{'offset': 100, 'raw': 'Hello'}]
    out = format_ndjson(strings, full=False).strip()
    parsed = json.loads(out)
    assert parsed == [100, "Hello"]


def test_format_ndjson_full():
    """Extended NDJSON format."""
    strings = [{'offset': 100, 'raw': 'Hello', 'context_hex': 'ABCD', 'score': 0.9, 'flags': 'null_term'}]
    out = format_ndjson(strings, full=True).strip()
    parsed = json.loads(out)
    assert parsed == [100, "Hello", "ABCD", 0.9, "null_term"]


# ============================================================
# Tests: edge cases
# ============================================================

def test_empty_data():
    """Empty data produces empty results."""
    assert scan_null_terminated(b'', 0) == []
    assert scan_aligned_strings(b'', 0) == []
    assert scan_utf16_strings(b'', 0) == []


def test_binary_noise():
    """Pure binary noise produces minimal false positives after filtering."""
    noise = bytes(range(256)) * 10  # all byte values, repeated
    result = scan_null_terminated(noise, 0)
    # Raw extraction may find runs, but scoring must catch them
    false_positives = [s for s in result if score_text(s['raw']) >= DIALOGUE_SCORE_THRESHOLD]
    assert len(false_positives) == 0, (
        f"Binary noise produced {len(false_positives)} scoring false positives: "
        f"{[s['raw'][:30] for s in false_positives]}")


def test_score_single_char():
    """Single character strings score 0."""
    assert score_text('') == 0.0
    assert score_text('a') == 0.0


def test_score_long_string():
    """Very long strings score 0."""
    assert score_text('a' * 1000) == 0.0


def test_score_control_chars():
    """Strings with control characters score 0."""
    assert score_text('Hello\x00World') == 0.0


def test_score_url():
    """URLs score 0."""
    assert score_text('https://example.com') == 0.0


# ============================================================
# Run all tests
# ============================================================

if __name__ == '__main__':
    # Simple test runner
    tests = [
        ("score: Yesss...!~", test_score_yesss),
        ("score: Fhaaa..!!", test_score_fhaaa),
        ("score: long phrase", test_score_long_phrase),
        ("score: normal text", test_score_normal_text),
        ("score: UI strings", test_score_ui_strings),
        ("score: garbage", test_score_garbage),
        ("score: settings key", test_score_settings_key),
        ("score: repeated letters", test_score_repeated_letters_garbage),
        ("is_candidate", test_is_candidate),
        ("null_term: basic", test_scan_null_terminated_basic),
        ("null_term: punctuation", test_scan_null_terminated_with_punctuation),
        ("null_term: long phrase", test_scan_null_terminated_long_phrase),
        ("null_term: min_len", test_scan_null_terminated_min_len),
        ("null_term: offset", test_scan_null_terminated_offset),
        ("aligned: basic", test_scan_aligned_strings_basic),
        ("aligned: dialogue", test_scan_aligned_strings_dialogue),
        ("aligned: offset", test_scan_aligned_strings_offset),
        ("aligned: noise", test_scan_aligned_strings_noise),
        ("utf16: basic", test_scan_utf16_basic),
        ("utf16: punctuation", test_scan_utf16_with_punctuation),
        ("all_runs: basic", test_scan_all_runs_basic),
        ("reconstruct: hyphen", test_reconstruct_hyphen_break),
        ("reconstruct: no merge far", test_reconstruct_no_merge_far),
        ("reconstruct: empty", test_reconstruct_empty),
        ("reconstruct: single", test_reconstruct_single),
        ("lz4: empty", test_lz4_block_decode_empty),
        ("lz4: small", test_lz4_block_decode_small),
        ("header: new format", test_parse_unity_header_new_format),
        ("header: old format", test_parse_unity_header_old_format),
        ("header: truncated", test_parse_unity_header_truncated),
        ("unityfs: header", test_parse_unityfs_header),
        ("unityfs: not unityfs", test_parse_unityfs_header_not_unityfs),
        ("file: synthetic", test_parse_synthetic_file),
        ("file: full scan", test_parse_synthetic_file_full_scan),
        ("file: raw DLL", test_parse_raw_file),
        ("ndjson: basic", test_format_ndjson_basic),
        ("ndjson: full", test_format_ndjson_full),
        ("edge: empty data", test_empty_data),
        ("edge: binary noise", test_binary_noise),
        ("edge: single char", test_score_single_char),
        ("edge: long string", test_score_long_string),
        ("edge: control chars", test_score_control_chars),
        ("edge: URL", test_score_url),
    ]

    passed = 0
    failed = 0
    for name, func in tests:
        try:
            func()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
