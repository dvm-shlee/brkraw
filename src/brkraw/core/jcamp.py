"""
Low-level JCAMP-DX parser for Bruker Paravision parameter files.

This module provides functional utilities to parse Paravision JCAMP-DX
formatted text (e.g., `method`, `acqp`, `reco` files) into a raw but structured
representation based on OrderedDicts. The goal is to preserve the original
hierarchical format as much as possible, while making it accessible to
downstream code.

Design choices:
- This module focuses on syntactic parsing only and keeps values in a
  minimally processed form.
- Higher-level normalization, type conversion, and object-oriented access
  are delegated to the `Parameters` class in `parameters.py`.
- The API is intentionally function-based (no classes) to keep the parsing
  logic small, composable, and easier to maintain.

The main entry point is `parse_jcamp_from_path`, which returns:
- `params`: an OrderedDict of parameter keys mapped to `{"shape", "data"}`
- `comments`: JCAMP comment lines (prefixed by `$$`)
- `exceptions`: raw lines or entries that could not be parsed cleanly

A simple smoke test utility `run_smoke_test` is provided to validate all
`.jdx` fixture files within a directory.
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import IO, Iterable, Union, Optional, List, Tuple, Any

logger = logging.getLogger(__name__)


REGEX_PATTERNS = {
    'value': re.compile(r'^\((?P<left>[^()]*)\)\s*(?P<right>.*)$'),
    'comment': re.compile(r'\$\$.*'),
}


def split_shape_and_data(string: Optional[str]):
    """Split a raw `(shape) value` string into shape metadata and payload.

    This function detects a leading parenthesized shape specification such as
    `(1, 2, 3) rest-of-value` and splits it into a shape tuple and the
    remaining string.

    Args:
        string: Raw JCAMP value that may start with a parenthesized shape.

    Returns:
        Tuple[Optional[Tuple[int, ...]], Optional[str]]:
            A pair `(shape, data)` where:

            - `shape` is a tuple of ints when a valid shape is present,
              otherwise None.
            - `data` is the remaining value string, or None if empty.
    """
    if not string:
        return None, None

    s = string.strip()
    if not s:
        return None, None

    m = REGEX_PATTERNS['value'].match(s)
    if not m:
        return None, s

    left_raw = m.group('left').strip()
    right_raw = m.group('right').strip()
    right_raw = right_raw or None

    shape_candidate = is_shape(left_raw)

    if shape_candidate is not None:
        return shape_candidate, right_raw
    return None, s


def is_shape(string: str):
    """Convert a comma-separated shape string into a tuple of ints if valid.

    This helper is used to interpret text such as `'1, 2, 3'` as a shape
    description.

    Args:
        string: Candidate shape string (for example `'1,2,3'`).

    Returns:
        Optional[Tuple[int, ...]]: A tuple of ints when parsing succeeds,
        otherwise None.
    """
    parts = [p.strip() for p in string.split(',')]
    int_values = []
    for p in parts:
        try:
            value = int(p)
        except ValueError:
            return None
        int_values.append(value)
    return tuple(int_values)


def to_number(token: str):
    """Convert a string token to an int or float when possible.

    Handles plain integers, floating point values, and exponential notation.
    If conversion fails, the original string is returned unchanged.

    Args:
        token: Raw token that may represent a number.

    Returns:
        Parsed numeric value (int/float) or the original token string.
    """
    token = token.strip()
    if not token:
        return token
    try:
        # Handle floats or exponential notation.
        if '.' in token or 'e' in token.lower():
            return float(token)
        return int(token)
    except ValueError:
        return token


def split_top_level_commas(s: str) -> List[str]:
    """Split a string on top-level commas while respecting nesting.

    Commas inside parentheses `(...)` or angle-bracketed blocks `<...>` are
    ignored. Only commas at depth 0 are treated as separators.

    Args:
        s: Input string that may contain parenthesized groups and angle
            brackets.

    Returns:
        List[str]: Substrings separated by top-level commas.
    """
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    angle_depth = 0
    escape = False

    for ch in s:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == '\\':
            buf.append(ch)
            escape = True
            continue

        if ch == '<':
            angle_depth += 1
            buf.append(ch)
        elif ch == '>':
            buf.append(ch)
            angle_depth = max(angle_depth - 1, 0)
        elif angle_depth == 0 and ch == '(':
            depth += 1
            buf.append(ch)
        elif angle_depth == 0 and ch == ')':
            depth -= 1
            buf.append(ch)
        elif angle_depth == 0 and ch == ',' and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)

    if buf:
        parts.append(''.join(buf).strip())

    return parts


def split_tokens_angle_aware(s: str) -> List[str]:
    """Tokenize by whitespace while keeping `<...>` blocks intact.

    Angle-bracketed sections such as `<PVM_SliceGeoObj>` are treated as
    indivisible tokens, even when they contain spaces.

    Args:
        s: Raw string possibly containing angle-bracketed sections.

    Returns:
        List[str]: Token list with angle-bracketed content preserved.
    """
    tokens: List[str] = []
    buf: List[str] = []
    angle_depth = 0
    escape = False

    for ch in s:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == '\\':
            buf.append(ch)
            escape = True
            continue

        if ch == '<':
            if buf and angle_depth == 0:
                tokens.append(''.join(buf))
                buf = []
            angle_depth += 1
            buf.append(ch)
        elif ch == '>':
            buf.append(ch)
            if angle_depth > 0:
                angle_depth -= 1
                if angle_depth == 0:
                    tokens.append(''.join(buf))
                    buf = []
        elif ch.isspace() and angle_depth == 0:
            if buf:
                tokens.append(''.join(buf))
                buf = []
        else:
            buf.append(ch)

    if buf:
        tokens.append(''.join(buf))

    return [t.strip() for t in tokens if t.strip()]


def is_single_outer_paren(s: str) -> bool:
    """Check whether the entire string is wrapped by a single outer pair.

    This function distinguishes between a single outer group:
        "(a b c)"
    and multiple outer groups:
        "(a b)(c d)"

    Angle-bracketed blocks `<...>` are ignored for the purpose of depth
    tracking.

    Args:
        s: Input string.

    Returns:
        bool: True if the string is wrapped by exactly one outer pair of
        parentheses, False otherwise.
    """
    s = s.strip()
    if not (s.startswith('(') and s.endswith(')')):
        return False

    depth = 0
    angle_depth = 0
    escape = False

    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue

        if ch == '<':
            angle_depth += 1
        elif ch == '>':
            angle_depth = max(angle_depth - 1, 0)
        elif angle_depth == 0:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth == 0 and i != len(s) - 1:
            # If depth hits 0 before the end, there are multiple outer groups.
            return False
    return depth == 0


def parse_leaf_tokens(text: str):
    """Parse whitespace-delimited tokens at a leaf level.

    This function expects a string without parentheses. It splits on whitespace,
    preserves `<...>` blocks as single tokens, and converts numeric tokens to
    int or float where possible.

    Args:
        text: Leaf-level string without parentheses.

    Returns:
        Any: Parsed value, which may be:
            - None for empty input
            - a single value (scalar or string)
            - a list of parsed values
    """
    tokens = split_tokens_angle_aware(text)
    values = [to_number(t) for t in tokens]

    if len(values) == 0:
        return None
    if len(values) == 1:
        return values[0]
    return values


def parse_segment(seg: str):
    """Parse a segment containing nested parentheses and leaf tokens.

    This function decomposes a substring that may include nested groups of
    parentheses and free-form tokens. Text at depth 0 is parsed as leaf
    tokens, while each nested `( ... )` group is parsed recursively via
    `parse_nested`.

    Args:
        seg: Substring potentially containing nested groups and leaf tokens.

    Returns:
        Any: Parsed object that may be:
            - None for empty segments
            - a single value
            - a list of values and/or nested structures
    """
    seg = seg.strip()
    if not seg:
        return None

    items: List[Any] = []
    buf: List[str] = []   # Text outside parentheses at depth 0.
    depth = 0
    start_idx = None
    angle_depth = 0
    escape = False

    for i, ch in enumerate(seg):
        if escape:
            if depth == 0:
                buf.append(ch)
            escape = False
            continue
        if ch == '\\':
            if depth == 0:
                buf.append(ch)
            escape = True
            continue

        if ch == '<':
            angle_depth += 1
            if depth == 0:
                buf.append(ch)

        elif ch == '>':
            if depth == 0:
                buf.append(ch)
            if angle_depth > 0:
                angle_depth -= 1

        elif angle_depth == 0 and ch == '(':
            if depth == 0:
                # Process buffered text before an opening parenthesis at depth 0.
                if buf:
                    leaf_text = ''.join(buf).strip()
                    if leaf_text:
                        leaf_val = parse_leaf_tokens(leaf_text)
                        if leaf_val is not None:
                            items.append(leaf_val)
                    buf = []
                start_idx = i
            depth += 1

        elif angle_depth == 0 and ch == ')':
            depth -= 1
            if depth == 0 and start_idx is not None:
                group_str = seg[start_idx:i+1]
                items.append(parse_nested(group_str))
                start_idx = None

        else:
            if depth == 0:
                buf.append(ch)
            # Content at depth > 0 will be handled in the group string.

    # Process any trailing text.
    if buf:
        leaf_text = ''.join(buf).strip()
        if leaf_text:
            leaf_val = parse_leaf_tokens(leaf_text)
            if leaf_val is not None:
                items.append(leaf_val)

    if len(items) == 0:
        return None
    if len(items) == 1:
        return items[0]
    return items


def parse_nested(s: str):
    """Parse JCAMP-style nested parentheses and comma-separated structures.

    This is the core recursive parser for Paravision/JCAMP text. It handles:
      - Optional outer parentheses
      - Top-level comma separation
      - Nested groups via `parse_segment`
      - Numeric token conversion via `to_number`

    Args:
        s: Raw string containing parentheses and comma-separated segments.

    Returns:
        Any: Parsed Python object corresponding to the nested structure, or
        None for empty input.
    """
    if s is None:
        return None

    s = s.strip()
    if not s:
        return None

    if "(" not in s and ")" not in s and "," not in s and " " not in s:
        return to_number(s)

    # 1) Strip outer parentheses if they wrap the entire content.
    while is_single_outer_paren(s):
        s = s[1:-1].strip()
        if not s:
            return []

    # 2) Split on top-level commas.
    parts = split_top_level_commas(s)

    # If there is no comma, treat the whole string as a single segment.
    if len(parts) == 1:
        return parse_segment(parts[0])

    # When multiple commas exist, parse each segment and return a list.
    results = []
    for part in parts:
        if not part.strip():
            continue
        val = parse_segment(part)
        if val is not None:
            results.append(val)

    return results


def _parse_lines(lines: Iterable[str]) -> dict:
    """Core parser that operates on an iterable of lines."""
    params = OrderedDict()
    comments: List[str] = []
    raw_params: List[str] = []
    exceptions: List[str] = []

    for raw in lines:
        line = raw.rstrip("\n")
        if REGEX_PATTERNS["comment"].match(line):
            comments.append(line.lstrip("$$").strip())
        else:
            raw_params.append(line)

    for param in " ".join(raw_params).split("##"):
        if not param:
            continue
        key, sep, value = param.strip().partition("=")
        if sep == "=":
            shape, data = split_shape_and_data(value)
            if isinstance(data, str):
                data = parse_nested(data)
            params[key] = {"shape": shape, "data": data}
        else:
            stripped = param.strip()
            if stripped:
                exceptions.append(stripped)

    return {"params": params, "comments": comments, "exceptions": exceptions}

def parse_jcamp_from_path(path: Path) -> dict:
    """Read a JCAMP/Paravision file from disk and parse it."""
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        return parse_jcamp(fp)


def parse_jcamp_from_text(text: str) -> dict:
    """Parse JCAMP text already loaded into memory (string)."""
    return _parse_lines(text.splitlines())


def parse_jcamp_from_bytes(data: Union[bytes, bytearray], *, encoding: str = "utf-8") -> dict:
    """Parse JCAMP content supplied as bytes."""
    return parse_jcamp_from_text(data.decode(encoding, errors="ignore"))


def parse_jcamp(stream: Union[IO[str], IO[bytes], Path, str, bytes, bytearray]) -> dict:
    """Generic parser that accepts path, str/bytes, or file-like objects."""
    # Path-like or str path
    if isinstance(stream, (str, Path)):
        return parse_jcamp_from_path(Path(stream))

    # Raw bytes/bytearray
    if isinstance(stream, (bytes, bytearray)):
        return parse_jcamp_from_bytes(stream)

    # File-like: attempt to read, resetting position if possible
    if hasattr(stream, "read"):
        reader = stream  # type: ignore[assignment]
        try:
            pos = reader.tell()  # type: ignore[attr-defined]
        except Exception:
            pos = None

        content = reader.read()  # type: ignore[call-arg]

        if pos is not None:
            try:
                reader.seek(pos)  # type: ignore[attr-defined]
            except Exception:
                pass

        if isinstance(content, (bytes, bytearray)):
            return parse_jcamp_from_bytes(content)
        elif isinstance(content, str):
            return parse_jcamp_from_text(content)

    raise TypeError(
        "Unsupported JCAMP source. Provide a Path/str, bytes, or file-like object."
    )


def run_smoke_test(fixtures_dir: Path) -> dict:
    """Run a smoke test over all `.jdx` files in a fixtures directory.

    For each `.jdx` file, this function attempts to parse JCAMP content and
    records whether parsing completed successfully and whether any exceptions
    were produced.

    This is intended as a lightweight regression check for the JCAMP parser.

    Args:
        fixtures_dir: Directory containing one or more `.jdx` JCAMP files.

    Returns:
        dict: Summary of the smoke test results with keys:

            - `total_files` (int):
                  Number of `.jdx` files processed.
            - `ok_files` (List[Path]):
                  Files that parsed without any recorded exceptions.
            - `files_with_exceptions` (List[Tuple[Path, List[str]]]):
                  Files that parsed but produced non-empty `exceptions`.
            - `parse_errors` (List[Tuple[Path, Exception]]):
                  Files that raised an exception during parsing.
    """
    summary = {
        "total_files": 0,
        "ok_files": [],
        "files_with_exceptions": [],
        "parse_errors": [],
    }

    for jdx_path in sorted(fixtures_dir.glob("*.jdx")):
        summary["total_files"] += 1
        logger.info(f"Parsing {jdx_path}")

        try:
            result = parse_jcamp_from_path(jdx_path)
        except Exception as exc:
            logger.error(f"Failed to parse {jdx_path}: {exc}")
            summary["parse_errors"].append((jdx_path, exc))
            continue

        exceptions = result.get("exceptions") or []
        if exceptions:
            logger.warning(
                f"Found {len(exceptions)} exceptions in {jdx_path}"
            )
            summary["files_with_exceptions"].append((jdx_path, exceptions))
        else:
            summary["ok_files"].append(jdx_path)

    return summary


__all__ = [
    "parse_jcamp_from_path", 
    "parse_jcamp_from_text", 
    "parse_jcamp_from_bytes", 
    "parse_jcamp", 
    "run_smoke_test"
    ]


def __dir__() -> List[str]:
    return sorted(__all__)
