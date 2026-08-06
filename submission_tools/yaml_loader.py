"""Small dependency-free loader for JSON-compatible YAML submission files.

YAML is a superset of JSON.  JSON-compatible YAML keeps this repository
dependency-light; a minimal indentation parser also supports ordinary mapping
and list syntax used in the documentation.  It intentionally does not attempt
to implement YAML anchors, tags, multiline scalars, or implicit date types.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") or value.startswith("{"):
        return json.loads(value)
    return value


def _lines(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))]:
            raise ValueError(f"tabs are not supported for indentation (line {line_no})")
        content = raw.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        out.append((len(content) - len(content.lstrip(" ")), content.strip()))
    return out


def _parse_block(rows: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(rows) or rows[index][0] < indent:
        return {}, index
    list_mode = rows[index][1].startswith("- ") or rows[index][1] == "-"
    value: Any = [] if list_mode else {}
    while index < len(rows) and rows[index][0] == indent:
        _, text = rows[index]
        if list_mode:
            if not (text.startswith("- ") or text == "-"):
                raise ValueError("cannot mix list and mapping values at one indentation level")
            item = text[1:].strip()
            index += 1
            if ":" in item and not item.startswith(("'", '"')):
                key, raw_value = item.split(":", 1)
                entry: dict[str, Any] = {key.strip(): _scalar(raw_value)}
                if index < len(rows) and rows[index][0] > indent:
                    nested, index = _parse_block(rows, index, rows[index][0])
                    if isinstance(nested, dict):
                        entry.update(nested)
                    else:
                        raise ValueError("list mapping continuation must be a mapping")
                value.append(entry)
            elif item:
                value.append(_scalar(item))
            elif index < len(rows) and rows[index][0] > indent:
                nested, index = _parse_block(rows, index, rows[index][0])
                value.append(nested)
            else:
                value.append(None)
        else:
            if ":" not in text:
                raise ValueError(f"expected key: value, got {text!r}")
            key, raw_value = text.split(":", 1)
            key = key.strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
                raise ValueError(f"unsupported key {key!r}")
            index += 1
            if raw_value.strip():
                value[key] = _scalar(raw_value)
            elif index < len(rows) and rows[index][0] > indent:
                value[key], index = _parse_block(rows, index, rows[index][0])
            else:
                value[key] = {}
    return value, index


def load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        rows = _lines(text)
        if not rows:
            raise ValueError("submission YAML is empty")
        loaded, index = _parse_block(rows, 0, rows[0][0])
        if index != len(rows):
            raise ValueError("unexpected trailing YAML content")
    if not isinstance(loaded, dict):
        raise ValueError("submission YAML must contain a mapping")
    return loaded
