#!/usr/bin/env python3
"""
parser_v2.py — Unity binary parser v2

Полная замена parser.mjs. Извлекает строки из Unity serialized файлов
(.assets, level*, .bundle, .dll) с dialogue-ориентированной фильтрацией
и реконструкцией фраз.

Output: Extended NDJSON: [offset, "raw", "context_hex", score, "flags"]

Flags:
  null_term    — null-terminated ASCII строка
  aligned      — length-prefixed aligned строка
  utf16        — UTF-16 LE строка
  reconstructed — собрана из соседних фрагментов
  bundle       — из AssetBundle
"""

import struct
import json

# Runtime NDJSON format: no spaces after commas (TranslationLoader expects ["key","val"])
def _j(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
import sys
import os
import re
import zlib
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# ============================================================
# Constants
# ============================================================

VERSION = "parse-unity v2 (python)"
MIN_LEN = 4
MAX_LEN = 500
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
RECONSTRUCT_MAX_GAP = 24  # max bytes between fragments to consider merging
DIALOGUE_SCORE_THRESHOLD = 0.25

GAME_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = GAME_DIR / "Third Crisis Neon Nights_Data"
BUNDLE_DIR = DATA_DIR / "StreamingAssets" / "aa" / "StandaloneWindows64"
DEFAULT_OUT = GAME_DIR / "output" / "parser"

# Dialogue punctuation that should NOT disqualify a string
DIALOGUE_PUNCTUATION = set("!?.,;:~-")

# ============================================================
# LZ4 Block Decoder (pure Python, zero deps)
# ============================================================

def lz4_block_decode(src: bytes, uncompressed_size: int) -> bytes:
    """Decode a single LZ4 block (legacy format, no CRC)."""
    dst = bytearray(uncompressed_size)
    sp = 0
    dp = 0

    while sp < len(src) and dp < uncompressed_size:
        token = src[sp]
        sp += 1
        lit_len = token >> 4
        match_len = (token & 0x0F) + 4

        if lit_len == 15:
            while True:
                add = src[sp]
                sp += 1
                lit_len += add
                if add != 255:
                    break

        # Copy literals
        chunk = src[sp:sp + lit_len]
        dst[dp:dp + len(chunk)] = chunk
        dp += len(chunk)
        sp += len(chunk)

        if sp >= len(src) or dp >= uncompressed_size:
            break

        # Match offset (2 bytes LE)
        if sp + 2 > len(src):
            break
        match_offset = src[sp] | (src[sp + 1] << 8)
        sp += 2

        if match_offset == 0:
            break

        if match_len == 19:
            while True:
                if sp >= len(src):
                    break
                add = src[sp]
                sp += 1
                match_len += add
                if add != 255:
                    break

        # Copy match
        match_pos = dp - match_offset
        for i in range(match_len):
            if dp >= uncompressed_size:
                break
            dst[dp] = dst[match_pos + i]
            dp += 1

    return bytes(dst[:dp])


def decompress_lz4_blocks(data: bytes, uncompressed_size: int, block_size: int = 0x8000) -> bytes:
    """Decompress concatenated LZ4 blocks."""
    result = bytearray()
    pos = 0
    while pos < len(data) and len(result) < uncompressed_size:
        if pos + 4 > len(data):
            break
        block_len = struct.unpack_from('<I', data, pos)[0]
        pos += 4

        if block_len == 0:
            break

        if block_len > uncompressed_size * 2:
            break

        if block_len < 0:
            # Uncompressed block
            uncomp_len = -block_len
            result.extend(data[pos:pos + uncomp_len])
            pos += uncomp_len
        else:
            # Compressed LZ4 block
            remaining = uncompressed_size - len(result)
            block = lz4_block_decode(data[pos:pos + block_len], min(block_size, remaining))
            result.extend(block)
            pos += block_len

    return bytes(result)


# ============================================================
# Character classification
# ============================================================

def is_printable_ascii(b: int, utf8: bool = True) -> bool:
    """
    Check if byte is a printable character.
    utf8=True: accept all bytes >= 32 (covers ASCII + UTF-8 multi-byte).
    utf8=False (legacy): strict 32-126 range.
    """
    if utf8:
        return b >= 32
    return 32 <= b <= 126


def is_letter_ascii(b: int) -> bool:
    return (65 <= b <= 90) or (97 <= b <= 122)


def is_utf8_continuation(b: int) -> bool:
    """Check if byte is a UTF-8 continuation byte (10xxxxxx)."""
    return 128 <= b <= 191


def is_utf8_start(b: int) -> bool:
    """Check if byte starts a multi-byte UTF-8 sequence."""
    return b >= 194  # 2-byte: 11000010+, 3-byte: 1110xxxx, 4-byte: 11110xxx


def decode_utf8_run(data: bytes) -> str:
    """Safely decode UTF-8 bytes, replacing errors."""
    return data.decode('utf-8', errors='replace')


def is_dialogue_punct_ascii(b: int) -> bool:
    return b in (ord(c) for c in '!?.,;:~-"\'')


# ============================================================
# String scoring — how likely is this to be dialogue/UI text?
# ============================================================

# ==== Code-suffix patterns (PascalCase that looks like code) ====
CODE_SUFFIXES = (
    'Settings', 'Behaviour', 'Component', 'Manager', 'Provider',
    'Factory', 'Service', 'Handler', 'Helper', 'Utility',
    'Provider', 'Engine', 'System', 'Base', 'Attribute',
    'Container', 'Collection', 'Builder', 'Loader', 'Writer',
    'Reader', 'Parser', 'Filter', 'Solver', 'Generator',
    'Listener', 'Emitter', 'Controller', 'Renderer',
)

# ==== Core extraction — find text nucleus inside surrounding symbols ====
CORE_MIN_LETTERS = 2  # minimum letters in core to be meaningful

DIALOGUE_CHARS = set("!?.,;:~-\"'")  # chars allowed in core + letters


def extract_core(text: str) -> str:
    """
    Find the longest contiguous sequence of letters + dialogue characters.
    This is the 'nucleus' of the string — what makes it translatable.
    """
    best = ''
    cur = ''
    for c in text:
        if c.isalpha() or c in DIALOGUE_CHARS:
            cur += c
            if len(cur) > len(best):
                best = cur
        else:
            cur = ''
    return best


def core_has_letters(core: str, min_count: int = CORE_MIN_LETTERS) -> bool:
    """Check if core has enough actual letters (not just punctuation)."""
    count = sum(1 for c in core if c.isalpha())
    return count >= min_count


# ==== English vowel/consonant helpers ====
VOWELS = set('aeiouyAEIOUY')

def has_vowels(word: str) -> bool:
    return any(c in VOWELS for c in word)


def score_text(text: str) -> float:
    """
    Score a string for dialogue/translation likelihood (0.0-1.0).
    Pure pattern-based — no hardcoded whitelists.
    """
    if not text or len(text) < 2 or len(text) > MAX_LEN:
        return 0.0

    n = len(text)

    # Control characters → garbage
    if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
        return 0.0

    # File paths and URLs → garbage
    if text.startswith('/') or text.startswith('\\'):
        return 0.0
    if '://' in text:
        return 0.0
    if re.match(r'^[A-Za-z]:[/\\]', text):
        return 0.0

    # First char should be alpha, digit, or dialogue punctuation
    if text[0].isalpha() or text[0] == '<':
        pass
    elif text[0] in DIALOGUE_PUNCTUATION and len(text) > 2:
        pass
    else:
        return 0.0

    # Code brackets/dollar/backtick → garbage
    if '[' in text or ']' in text:
        return 0.0
    if '{' in text or '}' in text:
        return 0.0
    if '$' in text:
        return 0.0
    if '|' in text:
        return 0.0
    if '`' in text:
        return 0.0
    if '\\\\' in text:
        return 0.0

    # Calculate metrics
    letters = sum(1 for c in text if c.isalpha())
    digits = sum(1 for c in text if c.isdigit())
    spaces = text.count(' ')
    punct = sum(1 for c in text if c in '!?.,;:~-"\'')
    words = len(text.split())

    letter_ratio = letters / n if n > 0 else 0
    digit_ratio = digits / n if n > 0 else 0

    # Unusual characters → garbage
    unusual = set('#$%&*+@[\\]^`{|}')  # no <> and no / — Unity rich text uses all three
    unusual_count = sum(1 for c in text if c in unusual)
    if unusual_count >= 1:
        return 0.0

    # Short strings with mixed letters/punct → check carefully
    if n <= 5 and punct > 0:
        if letters < 2:
            return 0.0
        if punct > letters:
            return 0.0

    # Single repeated character → garbage
    letters_only = ''.join(c for c in text if c.isalpha())
    if len(letters_only) >= 3 and len(set(letters_only)) == 1:
        return 0.0

    # Contains underscore → identifier
    if '_' in text:
        return 0.0

    # Contains parentheses → method calls
    if '(' in text or ')' in text:
        return 0.0

    # Forward slash without spaces → path (except rich text close tags)
    if '/' in text and ' ' not in text and not ('</' in text and text.endswith('>')):
        return 0.0

    # Settings.X keys → preserve (Unity ANToolkit pattern)
    if text.startswith('Settings.') and len(text) > 9:
        return 0.6

    # Dotted namespace: Word.Word
    if '.' in text:
        parts = text.split('.')
        if all(p and p[0].isupper() for p in parts):
            return 0.0
        if all(p and p[0].islower() for p in parts):
            return 0.0

    # ---- Multi-word strings (spaces) ----
    if spaces > 0:
        if letter_ratio >= 0.3:
            return 0.8
        return max(0.3, letter_ratio)

    # ---- Single word below ----
    # Single words are ambiguous: could be UI (Fullscreen) or code (QualitySettings)

    # Contains digits → code constant (RGBA32, DXT1)
    if digits > 0:
        return 0.0

    # All-caps, letters only, >1 char → acronym (PMA, FSM) or UI (OFF, ON)
    if text.isupper() and letters == n:
        if n <= 2:
            return 0.3  # short acronym, ambiguous
        if n >= 3 and not has_vowels(text):
            return 0.1  # no vowels → likely acronym
        return 0.4  # has vowels → could be UI word

    # camelCase starting with lowercase → code variable
    if re.match(r'^[a-z][a-zA-Z]*[A-Z]', text):
        return 0.0

    # PascalCase: identify compounds (uppercase inside)
    if text[0].isupper():
        # Count internal uppercase letters
        internal_upper = sum(1 for c in text[1:] if c.isupper())
        # Has compound boundaries (QualitySettings → internal 'S')
        if internal_upper > 0:
            return 0.1  # likely code compound
        # Ends with code-like suffix
        for suffix in CODE_SUFFIXES:
            if len(text) > len(suffix) and text.endswith(suffix):
                return 0.1
        # Pure single PascalCase word: could be UI
        # Long words with vowels → likely English
        if n >= 4 and has_vowels(text):
            return 0.5
        if n >= 2:
            return 0.3
        return 0.0

    # Lowercase single word
    if text.islower():
        if n >= 3 and has_vowels(text):
            return 0.4
        if n >= 3:
            return 0.2
        return 0.0

    # Short string: reject unnatural character patterns
    if n < 8:
        # Non-Latin letters in short string → likely garbage (English game)
        non_latin = sum(1 for c in text if c.isalpha() and not ('a' <= c <= 'z' or 'A' <= c <= 'Z'))
        if non_latin > 0:
            return 0.0
        # Latin letter case check: reject unnatural mixed case
        latin_letters = [c for c in text if 'a' <= c <= 'z' or 'A' <= c <= 'Z']
        if len(latin_letters) >= 2:
            is_pascal = (latin_letters[0].isupper() and all(c.islower() for c in latin_letters[1:]))
            all_upper = all(c.isupper() for c in latin_letters)
            all_lower = all(c.islower() for c in latin_letters)
            if not (all_lower or all_upper or is_pascal):
                return 0.0

    # Mixed case (not camelCase, not PascalCase) → could be dialogue word with punct
    # Emotional markers boost
    emotional_boost = 0.0
    if '!' in text:
        emotional_boost += 0.3
    if '~' in text:
        emotional_boost += 0.2
    if '..' in text:
        emotional_boost += 0.15
    if text.count('!') >= 2:
        emotional_boost += 0.1
    if text.count('.') >= 3:
        emotional_boost += 0.1

    # If has punctuation AND letters → likely dialogue word
    if punct > 0 and letter_ratio >= 0.35:
        return min(0.6 + emotional_boost, 1.0)

    # Low letter ratio but has emotional markers
    if letter_ratio < 0.2:
        if emotional_boost > 0.3:
            return min(emotional_boost, 0.8)
        return 0.0

    # Fallback: use letter ratio as base
    score = max(0.0, letter_ratio - 0.2 + emotional_boost)
    return min(score, 1.0)


def is_candidate(text: str, threshold: float = DIALOGUE_SCORE_THRESHOLD, full_scan: bool = False) -> bool:
    """Check if a string is a translation candidate."""
    if full_scan:
        return True
    return score_text(text) >= threshold


# ============================================================
# String extraction from raw binary
# ============================================================

def scan_null_terminated(data: bytes, base_offset: int = 0, min_len: int = MIN_LEN) -> List[Dict]:
    """
    Extract null-terminated strings.
    Scans for runs of printable ASCII (32-126) or valid UTF-8 multi-byte sequences.
    Uses core-based scoring: finds the text nucleus, scores it, keeps the full string.
    """
    result = []
    i = 0
    n = len(data)

    while i < n:
        b = data[i]
        # Strict ASCII printable (32-126)
        if 32 <= b <= 126:
            start = i
            cur = bytearray()
            while i < n and 32 <= data[i] <= 126:
                cur.append(data[i])
                i += 1
            s = cur.decode('ascii', errors='replace').strip()
            if len(s) >= min_len:
                core = extract_core(s)
                if core_has_letters(core, CORE_MIN_LETTERS):
                    ctx_start = max(0, start - 16)
                    ctx_end = min(n, i + 16)
                    context_hex = data[ctx_start:ctx_end].hex().upper()
                    result.append({
                        'offset': base_offset + start,
                        'raw': s,
                        'length': len(cur),
                        'context_hex': context_hex,
                        'score': score_text(core if len(core) < len(s) else s),
                        'flags': 'null_term',
                    })
        # UTF-8 multi-byte sequence start (>= 194)
        elif b >= 194 and i + 2 <= n:
            # Validate 2-byte sequence: 110xxxxx 10xxxxxx
            if 194 <= b <= 223 and 128 <= data[i+1] <= 191:
                start = i
                cur = bytearray()
                while i < n:
                    b2 = data[i]
                    if b2 >= 194:
                        # Check if valid start byte with continuation
                        needed = 1
                        if b2 >= 240:  # 4-byte
                            needed = 3
                        elif b2 >= 224:  # 3-byte
                            needed = 2
                        else:  # 2-byte
                            needed = 1
                        if i + needed < n and all(128 <= data[i+k] <= 191 for k in range(1, needed+1)):
                            cur.append(b2)
                            i += 1
                            for _ in range(needed):
                                cur.append(data[i])
                                i += 1
                        else:
                            break
                    elif 128 <= b2 <= 191:
                        # Orphan continuation → stop (likely binary noise)
                        break
                    elif 32 <= b2 <= 126:
                        cur.append(b2)
                        i += 1
                    else:
                        break
                else:
                    continue  # while fell off without break, continue outer
                # Decode the run
                try:
                    s = bytes(cur).decode('utf-8')
                except UnicodeDecodeError:
                    s = bytes(cur).decode('utf-8', errors='replace')
                s = s.strip()
                if len(s) >= min_len:
                    core = extract_core(s)
                    if core_has_letters(core, CORE_MIN_LETTERS):
                        ctx_start = max(0, start - 16)
                        ctx_end = min(n, i + 16)
                        context_hex = data[ctx_start:ctx_end].hex().upper()
                        result.append({
                            'offset': base_offset + start,
                            'raw': s,
                            'length': i - start,
                            'context_hex': context_hex,
                            'score': score_text(core if len(core) < len(s) else s),
                            'flags': 'null_term',
                        })
            else:
                i += 1
        else:
            i += 1

    return result


def scan_aligned_strings(data: bytes, base_offset: int = 0, min_len: int = 3) -> List[Dict]:
    """
    Extract length-prefixed aligned strings (Unity format).
    Scans for int32 LE length + UTF-8 data + padding.
    """
    result = []
    seen = set()

    i = 0
    while i < len(data):
        # Fast-forward to printable ASCII
        while i < len(data) and not is_printable_ascii(data[i]):
            i += 1
        if i >= len(data):
            break

        text_start = i

        # Measure text run
        text_len = 0
        while i + text_len < len(data) and is_printable_ascii(data[i + text_len]):
            text_len += 1
        i += text_len

        if text_len < min_len or text_len > 200:
            continue

        # Look for length prefix in 8 bytes before text_start
        for offset in range(-8, 0):
            prefix_pos = text_start + offset
            if prefix_pos < 0:
                continue
            if prefix_pos + 4 > len(data):
                continue

            stored_len = struct.unpack_from('<I', data, prefix_pos)[0]
            if stored_len < min_len or stored_len > 200:
                continue
            if prefix_pos + 4 + stored_len > len(data):
                continue

            candidate = data[prefix_pos + 4:prefix_pos + 4 + stored_len]
            try:
                candidate_str = candidate.decode('utf-8')
            except UnicodeDecodeError:
                candidate_str = candidate.decode('utf-8', errors='replace')

            if not candidate_str:
                continue

            # Verify: our text run should overlap with candidate
            text_snippet = data[text_start:text_start + min(text_len, 60)].decode('utf-8', errors='replace')
            if not text_snippet:
                continue
            if not text_snippet.startswith(candidate_str[:min(len(candidate_str), len(text_snippet))]):
                continue

            # Validate: must have letters
            letters = sum(1 for c in candidate_str if c.isalpha())
            if letters == 0:
                continue

            clean = candidate_str.strip()
            if len(clean) < min_len:
                continue

            key = f"{prefix_pos}:{clean}"
            if key in seen:
                continue
            seen.add(key)

            ctx_start = max(0, prefix_pos - 8)
            ctx_end = min(len(data), prefix_pos + 4 + stored_len + 8)
            context_hex = data[ctx_start:ctx_end].hex().upper()

            result.append({
                'offset': base_offset + prefix_pos,
                'raw': clean,
                'length': stored_len,
                'context_hex': context_hex,
                'score': score_text(clean),
                'flags': 'aligned',
            })
            break  # one match per text run

    return result


def scan_utf16_strings(data: bytes, base_offset: int = 0, min_len: int = MIN_LEN) -> List[Dict]:
    """
    Extract UTF-16 LE strings (e.g., .NET DLL #US heap).
    Two passes for even/odd alignment.
    """
    seen = {}

    for start_off in (0, 1):
        cur = []
        cur_start = 0

        for i in range(start_off, len(data) - 1, 2):
            lo = data[i]
            hi = data[i + 1]
            if 32 <= lo <= 126 and hi == 0:
                if not cur:
                    cur_start = i
                cur.append(lo)
            else:
                if cur:
                    s = bytes(cur).decode('ascii', errors='replace')
                    if len(s) >= min_len and cur_start not in seen:
                        letters = sum(1 for c in s if c.isalpha())
                        if letters > 0:
                            ctx_start = max(0, cur_start - 16)
                            ctx_end = min(len(data), cur_start + len(cur) * 2 + 16)
                            context_hex = data[ctx_start:ctx_end].hex().upper()
                            seen[cur_start] = {
                                'offset': base_offset + cur_start,
                                'raw': s.strip(),
                                'length': len(s),
                                'context_hex': context_hex,
                                'score': score_text(s.strip()),
                                'flags': 'utf16',
                            }
                    cur = []

        # Final check: string at end of buffer
        if cur and cur_start not in seen:
            s = bytes(cur).decode('ascii', errors='replace')
            if len(s) >= min_len:
                letters = sum(1 for c in s if c.isalpha())
                if letters > 0:
                    seen[cur_start] = {
                        'offset': base_offset + cur_start,
                        'raw': s.strip(),
                        'length': len(s),
                        'context_hex': '',
                        'score': score_text(s.strip()),
                        'flags': 'utf16',
                    }

    return sorted(seen.values(), key=lambda x: x['offset'])


def scan_all_runs(data: bytes, base_offset: int = 0, min_len: int = 3) -> List[Dict]:
    """
    Extract ALL printable ASCII runs including dialogue punctuation.
    This catches strings that null-term/aligned scanners miss.
    """
    result = []
    seen = set()
    cur = []
    start = 0

    for i, b in enumerate(data):
        if 32 <= b <= 126:
            if not cur:
                start = i
            cur.append(b)
        else:
            if cur:
                s = bytes(cur).decode('ascii', errors='replace')
                s = s.strip()
                if len(s) >= min_len and len(s) <= MAX_LEN:
                    key = f"{base_offset + start}:{s}"
                    if key not in seen:
                        seen.add(key)
                        letters = sum(1 for c in s if c.isalpha())
                        if letters > 0:
                            result.append({
                                'offset': base_offset + start,
                                'raw': s,
                                'length': len(cur),
                                'context_hex': '',
                                'score': score_text(s),
                                'flags': 'run',
                            })
                cur = []

    return result


# ============================================================
# Phrase reconstruction
# ============================================================

def reconstruct_phrases(strings: List[Dict], max_gap: int = RECONSTRUCT_MAX_GAP) -> List[Dict]:
    """
    Merge nearby string fragments that appear to be continuations.

    Heuristics:
    - Strings within max_gap bytes of each other
    - First fragment ends with continuation marker (-, ,, lowercase)
    - Second fragment starts with lowercase (continuation)
    - OR: fragments are very close (< 8 bytes) and have high individual scores
    """
    if not strings:
        return []

    sorted_strings = sorted(strings, key=lambda x: x['offset'])
    merged = []

    i = 0
    while i < len(sorted_strings):
        current = dict(sorted_strings[i])
        current['flags'] = current.get('flags', '')

        j = i + 1
        while j < len(sorted_strings):
            gap = sorted_strings[j]['offset'] - (current['offset'] + len(current['raw']))
            if gap < 0:
                j += 1
                continue
            if gap > max_gap:
                break

            prev_text = current['raw']
            next_text = sorted_strings[j]['raw']

            # Check for continuation patterns
            should_merge = False

            # Clear continuation: first ends with hyphen (split word)
            if prev_text.endswith('-'):
                should_merge = True

            # Clear continuation: first ends with comma, second starts lowercase
            elif prev_text.endswith(',') and next_text[0].islower() and gap < 8:
                should_merge = True

            # Moderate: no sentence-ending punctuation, second starts lowercase, very close
            elif not prev_text[-1] in '.!?' and next_text[0].islower() and gap < 4:
                should_merge = True

            # Fragments: both very short and extremely close — only if both are viable
            elif gap < 4 and len(prev_text) < 8 and len(next_text) < 8:
                prev_score = score_text(prev_text)
                next_score = score_text(next_text)
                if prev_score >= DIALOGUE_SCORE_THRESHOLD and next_score >= DIALOGUE_SCORE_THRESHOLD:
                    should_merge = True

            if should_merge:
                # Merge: add space if needed
                if prev_text and prev_text[-1] not in ' \t-,' and next_text[0] not in ' \t':
                    current['raw'] = prev_text + ' ' + next_text
                else:
                    current['raw'] = prev_text + next_text
                current['length'] = len(current['raw'].encode('utf-8', errors='replace'))
                current['score'] = max(current['score'], sorted_strings[j]['score'])
                current['flags'] = 'reconstructed'
                j += 1
            else:
                break

        merged.append(current)
        i = j

    return merged


# ============================================================
# Unity file format parsing
# ============================================================

def parse_unity_header(data: bytes) -> Optional[Dict]:
    """Parse Unity serialized file header."""
    # Detect format: Unity 2020+ (8 zero bytes) or old
    is_new = all(b == 0 for b in data[:8])

    if not is_new:
        # Old format (pre-2020)
        if len(data) < 20:
            return None
        metadata_size = struct.unpack_from('<I', data, 0)[0]
        file_size = struct.unpack_from('<I', data, 4)[0]
        version = struct.unpack_from('<I', data, 8)[0]
        data_offset = struct.unpack_from('<I', data, 12)[0]
        endian = data[16]
        return {
            'version': version,
            'data_offset': data_offset,
            'metadata_size': metadata_size,
            'file_size': file_size,
            'endianess': endian,
            'big_endian': endian == 1,
            'header_size': 20,
            'metadata_offset': 20,
            'new_format': False,
        }

    # New format (Unity 2020+): bytes 0-7 zeros, rest BE
    if len(data) < 48:
        return None
    version = struct.unpack_from('>i', data, 8)[0]
    data_offset = struct.unpack_from('>i', data, 36)[0]
    metadata_size = struct.unpack_from('>i', data, 20)[0]
    file_size = struct.unpack_from('>i', data, 28)[0]
    endian = data[16]
    metadata_offset = data_offset - metadata_size

    # Null-terminated Unity version string
    ver_end = 48
    while ver_end < len(data) and data[ver_end] != 0:
        ver_end += 1
    unity_version = data[48:ver_end].decode('utf-8', errors='replace')

    return {
        'version': version,
        'data_offset': data_offset,
        'metadata_size': metadata_size,
        'file_size': file_size,
        'endianess': endian,
        'big_endian': endian == 1,
        'header_size': metadata_offset if metadata_offset > 0 else 48,
        'metadata_offset': metadata_offset,
        'new_format': True,
        'unity_version': unity_version,
    }


def parse_unityfs_header(data: bytes) -> Optional[Dict]:
    """Parse UnityFS (AssetBundle) header."""
    if data[:7] != b'UnityFS':
        return None
    if len(data) < 64:
        return None

    compressed_header_size = struct.unpack_from('>I', data, 38)[0]
    decompressed_header_size = struct.unpack_from('>I', data, 42)[0]
    flags = struct.unpack_from('>I', data, 46)[0]
    compression_type = flags & 0x3F

    return {
        'compressed_header_size': compressed_header_size,
        'decompressed_header_size': decompressed_header_size,
        'compression_type': compression_type,
        'header_start': 64,
        'data_start': 64 + compressed_header_size,
    }


# ============================================================
# Dialogue history extraction (Speaker/Text pairs)
# ============================================================

def extract_json_string(data: bytes, start: int) -> Tuple[Optional[str], int]:
    """Extract a JSON string from binary data starting after the opening quote."""
    i = start
    chars = []
    while i < len(data):
        b = data[i]
        if b == 0x22:  # double quote
            return ''.join(chars), i + 1
        elif b == 0x5C:  # backslash
            if i + 1 < len(data):
                nxt = data[i + 1]
                if nxt in (0x22, 0x5C, 0x6E, 0x72, 0x74):  # ", \, n, r, t
                    chars.append(chr(nxt))
                    i += 2
                elif nxt == 0x75:  # u (unicode escape)
                    if i + 5 < len(data):
                        try:
                            hex_str = data[i+2:i+6].decode('ascii')
                            chars.append(chr(int(hex_str, 16)))
                            i += 6
                        except:
                            i += 2
                    else:
                        i += 2
                else:
                    chars.append(chr(nxt))
                    i += 2
            else:
                break
        else:
            chars.append(chr(b))
            i += 1
    return None, i


def scan_dialogue_history(data: bytes, base_offset: int = 0) -> List[Dict]:
    """
    Extract Speaker/Text pairs from ANToolkit DialogueHistory format.

    Looks for: {"Speaker":"...","Text":"...","SpeakerColor":"...","IsChoice":...}
    Returns list ordered by appearance in binary (game sequence).
    """
    results = []
    seen_texts = set()
    i = 0
    marker = b'"Speaker":"'
    text_marker = b',"Text":"'

    while i < len(data):
        pos = data.find(marker, i)
        if pos < 0:
            break

        sp, end = extract_json_string(data, pos + len(marker))
        if sp is None:
            i = pos + 1
            continue

        text_pos = data.find(text_marker, end)
        if text_pos < 0:
            i = end
            continue

        tx, end2 = extract_json_string(data, text_pos + len(text_marker))
        if tx is None:
            i = text_pos + 1
            continue

        # Extract SpeakerColor if available
        color = ''
        color_marker = b',"SpeakerColor":"'
        color_pos = data.find(color_marker, end2)
        if 0 <= color_pos - end2 < 50:
            col, _ = extract_json_string(data, color_pos + len(color_marker))
            if col:
                color = col

        # Strip rich text for clean version
        clean = re.sub(r'<[^>]+>', '', tx).strip()

        # Skip empty text
        if not clean:
            i = end2
            continue

        # Deduplicate identical pairs (dialogue replay)
        dedup_key = f"{sp}|{clean}"
        if dedup_key not in seen_texts:
            seen_texts.add(dedup_key)
            results.append({
                'offset': base_offset + pos,
                'speaker': sp if sp else '',
                'text': tx,
                'clean': clean,
                'speaker_color': color,
                'score': 1.0,  # dialogue is always valid
            })

        i = end2

    return results


def format_dialogue_ndjson(pairs: List[Dict], full: bool = False,
                           target_format: bool = False) -> str:
    """
    Format dialogue pairs as NDJSON.

    Basic:    [seq_index,"Speaker","clean_text"]
    Full:     [seq_index,"Speaker","clean_text","rich_text",offset,"color"]
    Target:   ["clean_text","","Speaker"]  (for runtime: eng, rus, speaker)
    """
    lines = []
    for idx, p in enumerate(pairs):
        if target_format:
            entry = _j([p['clean'], '', p['speaker']])
        elif full:
            entry = _j([idx, p['speaker'], p['clean'], p['text'],
                        p['offset'], p.get('speaker_color', '')])
        else:
            entry = _j([idx, p['speaker'], p['clean']])
        lines.append(entry)
    return '\n'.join(lines) + '\n'


# ============================================================
# File-level parsing
# ============================================================

def parse_unity_file(filepath: Path, options: Dict) -> Dict:
    """Parse a Unity serialized file (.assets, level*)."""
    data = filepath.read_bytes()
    if len(data) > MAX_FILE_SIZE:
        data = data[:MAX_FILE_SIZE]

    header = parse_unity_header(data)
    if header is None:
        return {'name': filepath.stem, 'path': str(filepath), 'type': 'unity',
                'error': 'Could not parse Unity header', 'strings': []}

    data_offset = header['data_offset']
    data_end = data_offset + (header.get('file_size', len(data)) - data_offset)
    data_end = min(data_end, len(data))
    data_section = data[data_offset:data_end]

    min_len = options.get('min_len', MIN_LEN)
    full_scan = options.get('full_scan', False)
    do_reconstruct = options.get('reconstruct', True)

    # Extract using all methods
    null_term = scan_null_terminated(data_section, data_offset, min_len)
    aligned = scan_aligned_strings(data_section, data_offset, min_len)
    utf16 = scan_utf16_strings(data_section, data_offset, min_len)
    runs = scan_all_runs(data_section, data_offset, min_len)

    # Merge and deduplicate by offset
    all_by_offset = {}
    for s in null_term + aligned + utf16 + runs:
        off = s['offset']
        if off not in all_by_offset or s['flags'] == 'aligned':
            all_by_offset[off] = s
        elif s['flags'] == 'null_term' and all_by_offset[off].get('flags') in ('run',):
            all_by_offset[off] = s
        elif len(s.get('raw', '')) > len(all_by_offset[off].get('raw', '')):
            all_by_offset[off] = s

    all_strings = sorted(all_by_offset.values(), key=lambda x: x['offset'])

    # Filter by score
    threshold = options.get('threshold', DIALOGUE_SCORE_THRESHOLD)
    raw_count = len(all_strings)
    filtered = [s for s in all_strings if is_candidate(s['raw'], threshold, full_scan)]

    # Reconstruct phrases
    if do_reconstruct and not full_scan:
        filtered = reconstruct_phrases(filtered)

    return {
        'name': filepath.stem,
        'path': str(filepath),
        'type': 'unity',
        'header': {k: v for k, v in header.items() if k in ('version', 'file_size', 'data_offset',
                   'metadata_offset', 'metadata_size', 'unity_version', 'new_format')},
        'strings': filtered,
        'stats': {
            'total_strings': len(filtered),
            'total_raw': raw_count,
            'filtered_out': raw_count - len(filtered),
            'null_terminated': len(null_term),
            'aligned': len(aligned),
            'utf16': len(utf16),
            'runs': len(runs),
        },
    }


def parse_raw_file(filepath: Path, options: Dict) -> Dict:
    """Parse a raw binary file (e.g., DLL)."""
    data = filepath.read_bytes()
    if len(data) > MAX_FILE_SIZE:
        data = data[:MAX_FILE_SIZE]

    min_len = options.get('min_len', MIN_LEN)
    full_scan = options.get('full_scan', False)

    ascii_strings = scan_null_terminated(data, 0, min_len)
    utf16_strings = scan_utf16_strings(data, 0, min_len)

    all_by_offset = {}
    for s in ascii_strings + utf16_strings:
        off = s['offset']
        if off not in all_by_offset or len(s.get('raw', '')) > len(all_by_offset[off].get('raw', '')):
            all_by_offset[off] = s

    all_strings = sorted(all_by_offset.values(), key=lambda x: x['offset'])

    threshold = options.get('threshold', DIALOGUE_SCORE_THRESHOLD)
    raw_count = len(all_strings)
    filtered = [s for s in all_strings if is_candidate(s['raw'], threshold, full_scan)]

    return {
        'name': filepath.stem,
        'path': str(filepath),
        'type': 'raw',
        'file_size': len(data),
        'strings': filtered,
        'stats': {
            'total_strings': len(filtered),
            'total_raw': raw_count,
            'filtered_out': raw_count - len(filtered),
        },
    }


def parse_bundle_file(filepath: Path, options: Dict) -> Dict:
    """Parse an AssetBundle (.bundle) file."""
    data = filepath.read_bytes()
    if len(data) > MAX_FILE_SIZE:
        data = data[:MAX_FILE_SIZE]

    hdr = parse_unityfs_header(data)
    if hdr is None:
        return {'name': filepath.stem, 'path': str(filepath), 'type': 'bundle',
                'error': 'Not a UnityFS bundle', 'strings': []}

    if hdr['compression_type'] == 3:
        # LZ4 compressed
        comp_header = data[hdr['header_start']:hdr['header_start'] + hdr['compressed_header_size']]
        try:
            decomp_header = decompress_lz4_blocks(comp_header, hdr['decompressed_header_size'])
        except Exception as e:
            return {'name': filepath.stem, 'path': str(filepath), 'type': 'bundle',
                    'error': f'LZ4 decompression failed: {e}', 'strings': []}

        # Data area is raw/uncompressed after the header
        data_area = data[hdr['data_start']:]
    else:
        data_area = data[hdr['data_start']:]

    min_len = options.get('min_len', MIN_LEN)
    full_scan = options.get('full_scan', False)
    threshold = options.get('threshold', DIALOGUE_SCORE_THRESHOLD)

    all_strings = scan_null_terminated(data_area, hdr['data_start'], min_len)
    raw_count = len(all_strings)
    filtered = [s for s in all_strings if is_candidate(s['raw'], threshold, full_scan)]

    # Tag bundle strings
    for s in filtered:
        if 'flags' not in s or not s['flags']:
            s['flags'] = 'bundle'
        else:
            s['flags'] += '+bundle'

    return {
        'name': filepath.stem,
        'path': str(filepath),
        'type': 'bundle',
        'file_size': len(data),
        'strings': filtered,
        'stats': {
            'total_strings': len(filtered),
            'total_raw': raw_count,
            'filtered_out': raw_count - len(filtered),
        },
    }


def parse_dialogue_file(filepath: Path, options: Dict) -> Dict:
    """Extract Speaker/Text dialogue pairs from Unity file."""
    data = filepath.read_bytes()
    if len(data) > MAX_FILE_SIZE:
        data = data[:MAX_FILE_SIZE]

    pairs = scan_dialogue_history(data)
    full_format = options.get('full_format', True)
    target_format = options.get('target_format', False)

    return {
        'name': filepath.stem,
        'path': str(filepath),
        'type': 'dialogue',
        'file_size': len(data),
        'pairs': pairs,
        'stats': {
            'total_pairs': len(pairs),
        },
        'ndjson': format_dialogue_ndjson(pairs, full=full_format, target_format=target_format),
    }


# ============================================================
# Default file discovery
# ============================================================

def get_default_files() -> List[Tuple[str, Path, str]]:
    """Return list of (name, path, type) for default game files."""
    files = []

    # Level files
    for i in range(16):
        p = DATA_DIR / f'level{i}'
        if p.exists():
            files.append((f'level{i}', p, 'unity'))

    # Shared assets
    for i in range(16):
        p = DATA_DIR / f'sharedassets{i}.assets'
        if p.exists():
            files.append((f'sharedassets{i}', p, 'unity'))

    # Resources
    for p in [DATA_DIR / 'resources.assets', DATA_DIR / 'globalgamemanagers.assets']:
        if p.exists():
            files.append((p.stem, p, 'unity'))

    # Managed DLLs
    managed = DATA_DIR / 'Managed'
    for dll in ['Assembly-CSharp.dll', 'Assembly-CSharp-firstpass.dll']:
        p = managed / dll
        if p.exists():
            files.append((p.stem, p, 'raw'))

    return files


# ============================================================
# NDJSON output
# ============================================================

def format_ndjson(strings: List[Dict], full: bool = False) -> str:
    """
    Format strings as extended NDJSON.

    Basic: [offset, "raw"]
    Full:  [offset, "raw", "context_hex", score, "flags"]
    """
    lines = []
    for s in strings:
        if full:
            entry = json.dumps([
                s['offset'],
                s['raw'],
                s.get('context_hex', ''),
                round(s.get('score', 0), 3),
                s.get('flags', ''),
            ], ensure_ascii=False)
        else:
            entry = json.dumps([s['offset'], s['raw']], ensure_ascii=False)
        lines.append(entry)
    return '\n'.join(lines) + '\n'


# ============================================================
# CLI
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Unity binary parser v2 — extract dialogue and UI strings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parser_v2.py
  python parser_v2.py --level 3
  python parser_v2.py --file "path/to/file.assets" --type unity
  python parser_v2.py --file "path/to/file.dll" --type raw
  python parser_v2.py --full
  python parser_v2.py --min-len 8
  python parser_v2.py --threshold 0.5
  python parser_v2.py --out output/parser-v2/
        """)

    parser.add_argument('--level', type=int, help='Parse single level (0-15)')
    parser.add_argument('--file', type=str, help='Parse specific file')
    parser.add_argument('--name', type=str, help='Name for the file (defaults to filename)')
    parser.add_argument('--type', type=str, choices=['unity', 'raw', 'bundle'], default=None,
                        help='File type (auto-detected if not specified)')
    parser.add_argument('--out', type=str, default=None, help='Output directory')
    parser.add_argument('--min-len', type=int, default=MIN_LEN, help=f'Minimum string length (default: {MIN_LEN})')
    parser.add_argument('--threshold', type=float, default=DIALOGUE_SCORE_THRESHOLD,
                        help=f'Dialogue score threshold 0-1 (default: {DIALOGUE_SCORE_THRESHOLD})')
    parser.add_argument('--full', action='store_true', help='Full scan: extract all strings, no filtering')
    parser.add_argument('--no-reconstruct', action='store_true', help='Disable phrase reconstruction')
    parser.add_argument('--no-defaults', action='store_true', help='Do not include default files')
    parser.add_argument('--bundle', action='store_true', help='Scan bundle files')
    parser.add_argument('--dialogue', action='store_true',
                        help='Extract Speaker/Text dialogue pairs (structured)')
    parser.add_argument('--texts', action='store_true',
                        help='Extract UI/system texts (deduplicated)')
    parser.add_argument('--characters', action='store_true',
                        help='Extract unique speaker names to characters.ndjson')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()
    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    options = {
        'min_len': args.min_len,
        'full_scan': args.full,
        'threshold': args.threshold,
        'reconstruct': not args.no_reconstruct,
        'target_format': True,
    }

    # Dialogue mode: extract Speaker/Text pairs
    if args.dialogue:
        # Scan resources.assets for dialogue history
        fp = DATA_DIR / 'resources.assets'
        if not fp.exists():
            print(f"ERROR: resources.assets not found", file=sys.stderr)
            sys.exit(1)
        result = parse_dialogue_file(fp, options)
        pairs = result['pairs']
        print(f"Dialogue: {len(pairs)} Speaker/Text pairs", file=sys.stderr)

        # Write dialogue NDJSON to translations/dialogs/
        dialogs_dir = GAME_DIR / 'translations' / 'dialogs'
        dialogs_dir.mkdir(parents=True, exist_ok=True)
        out_path = dialogs_dir / 'dialogue.ndjson'
        out_path.write_text(result['ndjson'], encoding='utf-8')
        print(f"  -> {out_path}", file=sys.stderr)

        # Also write summary
        from collections import Counter
        sp_counts = Counter(p['speaker'] for p in pairs)
        print(f"\nSpeakers:", file=sys.stderr)
        for sp, cnt in sp_counts.most_common():
            print(f"  {sp or '(narration)'}: {cnt}", file=sys.stderr)
        return

    # Texts mode: extract UI/system strings
    if args.texts:
        import json as _json
        from collections import OrderedDict

        def _display_from_key(key: str) -> str:
            """Settings.Fullscreen -> Fullscreen. Reject compound keys."""
            display = key[9:] if key.startswith('Settings.') else key
            # Reject if there's a second dot (compound key)
            if '.' in display:
                return ''
            return display

        texts_dir = GAME_DIR / 'translations' / 'texts'
        texts_dir.mkdir(parents=True, exist_ok=True)

        # ---- 1. Extract UI display texts from Settings key suffix ----
        def _split_camel(s: str) -> str:
            """AlwaysSprint -> Always Sprint"""
            result = []
            for i, c in enumerate(s):
                if i > 0 and c.isupper() and (s[i-1].islower() or (i+1 < len(s) and s[i+1].islower())):
                    result.append(' ')
                result.append(c)
            return ''.join(result)

        ui_display = set()
        try:
            fp = DATA_DIR / 'resources.assets'
            data = fp.read_bytes()
            for s in scan_null_terminated(data, 0, 2):
                raw = s['raw']
                if raw.startswith('Settings.') and len(raw) > 9:
                    d = _display_from_key(raw)
                    if d and d[0].isupper() and len(d) >= 3 and len(d) <= 40:
                        ui_display.add(_split_camel(d))
        except Exception as e:
            print(f"Settings extraction failed: {e}", file=sys.stderr)

        # ---- 3. Deduplicate display texts ----
        # Remove strings that look like dialogue (sentence-like, >5 words)
        ui_display = {s for s in ui_display
                      if len(s.split()) <= 5
                      and not s.endswith(('.', '!', '?'))
                      and not s.startswith(('-', '.', ','))}

        # ---- 4. Add ANToolkit-specific UI patterns from resources ----
        # Known Settings.X display texts (fallback for non-extractable)
        known_display = {
            'Fullscreen', 'Windowed', 'Resolution', 'VSync', 'Enable VSync',
            'Quality', 'Low', 'Medium', 'High', 'Ultra', 'Extreme',
            'Master Volume', 'Music Volume', 'Effects Volume',
            'Language', 'Always Sprint',
            'Dialogue Autoplay', 'Off', 'Normal', 'Fast', 'Slow',
            'Controls Tab', 'Dynamic Lighting',
            'Shadow Quality', 'Texture Quality', 'Bloom',
            'Ambient Occlusion', 'Depth of Field', 'Motion Blur',
            'Show Advanced Performance Stats',
            'Save Slot', 'Auto Save', 'Quick Save',
            'Save Game', 'Load Game', 'New Game', 'Continue',
            'Options', 'Settings', 'Controls', 'Audio', 'Video', 'Graphics',
            'Display', 'Gameplay', 'Exit', 'Quit', 'Volume',
            'Back', 'Cancel', 'Confirm', 'Apply',
            'Default', 'Reset', 'Restore Defaults',
            'Delete', 'Save', 'Load',
            'Anti-aliasing', 'Anisotropic Filtering',
            'Xbox', 'PlayStation', 'Controller', 'Keyboard', 'Mouse',
            'Key Bindings',
            'Master/VA/VA Internal Monologue',
        }
        ui_display |= known_display

        # ---- 5. Write ui.ndjson ----
        sorted_ui = sorted(ui_display, key=lambda x: (-len(x), x))
        ui_lines = [_j([s, '']) for s in sorted_ui]
        ui_path = texts_dir / 'ui.ndjson'
        ui_path.write_text('\n'.join(ui_lines) + '\n', encoding='utf-8')
        print(f"UI texts: {len(ui_lines)} unique strings -> {ui_path}", file=sys.stderr)
        for line in ui_lines[:20]:
            print(f'  {line}', file=sys.stderr)
        return

    # Characters mode: extract unique speaker names
    if args.characters:
        fp = DATA_DIR / 'resources.assets'
        if not fp.exists():
            print(f"ERROR: resources.assets not found", file=sys.stderr)
            sys.exit(1)
        result = parse_dialogue_file(fp, options)
        pairs = result['pairs']

        from collections import Counter
        sp_counts = Counter(p['speaker'] for p in pairs)

        # Gender hints for known characters
        GENDER_HINTS = {
            'Zoey': 'ж',
            'Sarah': 'ж',
            'Woman': 'ж',
            'Klaudia': 'ж',
            'Leona': 'ж',
            'Rosie': 'ж',
            'Skank': 'ж',
            'Nova': 'ж',
            'Salon Clerk': 'ж',
            '???': '',
            'Man': 'м',
            'Max': 'м',
            'Lio': 'м',
            'Klark': 'м',
            'Customer': '',
            'Jay': 'м',
            'Cartel Guy': 'м',
            'Jaime': 'м',
            'The Boss': '',
            'Enforcer 1483': 'м',
            'Enforcer 1520': 'м',
            'Hooligan': 'м',
            'Intercom': '—',
            '(narration)': '—',
        }

        entries = []
        for sp, cnt in sp_counts.most_common():
            gender = GENDER_HINTS.get(sp, '')
            entries.append(_j([sp, '', gender]))

        chars_dir = GAME_DIR / 'translations'
        chars_dir.mkdir(parents=True, exist_ok=True)
        chars_path = chars_dir / 'characters.ndjson'
        chars_path.write_text('\n'.join(entries) + '\n', encoding='utf-8')

        print(f"Characters: {len(entries)} unique speakers -> {chars_path}", file=sys.stderr)
        for e in entries:
            print(f'  {e}', file=sys.stderr)
        return

    # Determine file list
    files = []

    if args.file:
        fp = Path(args.file)
        if not fp.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        ftype = args.type
        if ftype is None:
            if fp.suffix == '.bundle':
                ftype = 'bundle'
            elif fp.suffix == '.dll':
                ftype = 'raw'
            else:
                ftype = 'unity'
        files.append((args.name or fp.stem, fp, ftype))

    elif args.level is not None:
        fp = DATA_DIR / f'level{args.level}'
        if not fp.exists():
            print(f"ERROR: level{args.level} not found", file=sys.stderr)
            sys.exit(1)
        files.append((f'level{args.level}', fp, 'unity'))

    elif args.bundle:
        if not BUNDLE_DIR.exists():
            print(f"ERROR: Bundle directory not found: {BUNDLE_DIR}", file=sys.stderr)
            sys.exit(1)
        target_patterns = ['level-', '3dsuitcasescene', 'releasenotesui']
        all_bundles = sorted(BUNDLE_DIR.glob('*.bundle'))
        for bf in all_bundles:
            if any(p in bf.name for p in target_patterns):
                files.append((bf.stem, bf, 'bundle'))

    elif not args.no_defaults:
        files = get_default_files()

    else:
        print("ERROR: No files specified. Use --level, --file, --bundle, or omit --no-defaults.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Parser v2: {len(files)} file(s) to scan, min length {args.min_len}, "
          f"threshold {args.threshold}", file=sys.stderr)

    if args.full:
        print("  Full scan mode (no filtering)", file=sys.stderr)

    # Parse files
    results = []
    for name, fp, ftype in files:
        try:
            if ftype == 'unity':
                result = parse_unity_file(fp, options)
            elif ftype == 'raw':
                result = parse_raw_file(fp, options)
            elif ftype == 'bundle':
                result = parse_bundle_file(fp, options)
            else:
                continue

            if 'error' in result:
                print(f"  {name}: ERROR - {result['error']}", file=sys.stderr)
                continue

            # Apply min_len filter
            if args.min_len > MIN_LEN:
                result['strings'] = [s for s in result['strings'] if len(s['raw']) >= args.min_len]
                result['stats']['total_strings'] = len(result['strings'])

            results.append(result)

            stats = result['stats']
            filtered = stats.get('filtered_out', 0)
            print(f"  {name}: {stats['total_strings']} strings"
                  f" (raw {stats['total_raw']}, filtered {filtered})"
                  f" — {ftype}", file=sys.stderr)

        except Exception as e:
            print(f"  {name}: ERROR - {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()

    # Write output
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        'parser': VERSION,
        'timestamp': None,  # filled by __import__('datetime')
        'full_scan': args.full,
        'min_length': args.min_len,
        'threshold': args.threshold,
        'reconstruct': options['reconstruct'],
        'total_files': len(results),
        'total_strings': sum(r['stats']['total_strings'] for r in results),
        'total_filtered_out': sum(r['stats'].get('filtered_out', 0) for r in results),
        'files': [{
            'name': r['name'],
            'type': r['type'],
            'header': r.get('header'),
            'file_size': r.get('file_size'),
            'stats': r['stats'],
        } for r in results],
    }

    import datetime
    manifest['timestamp'] = datetime.datetime.now().isoformat()

    # Write manifest
    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), 'utf-8')

    # Write per-file NDJSON (basic format for compatibility)
    written = 0
    for r in results:
        lines = format_ndjson(r['strings'], full=args.full)
        (out_dir / f"{r['name']}.ndjson").write_text(lines, 'utf-8')
        written += len(r['strings'])

    # Also write extended format
    ext_strings = []
    for r in results:
        for s in r['strings']:
            ext_strings.append(s)
    if ext_strings:
        ext_lines = json.dumps({
            'parser': VERSION,
            'timestamp': manifest['timestamp'],
            'threshold': args.threshold,
            'strings': ext_strings,
        }, indent=2, ensure_ascii=False)
        (out_dir / 'extended.json').write_text(ext_lines, 'utf-8')

    print(f"\n{manifest['total_strings']} strings → {len(results)} NDJSON files", file=sys.stderr)
    print(f"  manifest: {out_dir / 'manifest.json'}", file=sys.stderr)
    print(f"  data:     {out_dir / '*.ndjson'}", file=sys.stderr)
    if args.full:
        print(f"  extended: {out_dir / 'extended.json'}", file=sys.stderr)


if __name__ == '__main__':
    main()
