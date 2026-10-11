from __future__ import annotations

import json
import re


def _strip_comment(value: str) -> str:
    quote: str | None = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if quote == "'" and char == "'" and value[index:index + 2] == "''":
            index += 2
            continue
        if char == quote:
            quote = None
        elif quote is None and char in "\"'" and (
            not value[:index].strip() or value[:index].rstrip().endswith(("[", ","))
        ):
            quote = char
        elif quote is None and char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1
    if quote is not None:
        raise ValueError("Unclosed quote")
    return value.strip()


def _split_list(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    quote: str | None = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if quote == "'" and value[index:index + 2] == "''":
            index += 2
            continue
        if char == quote:
            quote = None
        elif quote is None and char in "\"'" and not value[start:index].strip():
            quote = char
        elif quote is None and char == ",":
            items.append(value[start:index].strip())
            start = index + 1
        elif quote is None and char in "[]{}":
            raise ValueError("Nested collections are unsupported")
        index += 1
    if quote is not None:
        raise ValueError("Unclosed quote")
    items.append(value[start:].strip())
    if any(not item for item in items):
        raise ValueError("Empty list item")
    return items


def _scalar(value: str) -> object:
    value = _strip_comment(value)
    if not value:
        return None
    if value.startswith('"'):
        result = json.loads(value)
        if not isinstance(result, str):
            raise ValueError("Expected quoted text")
        return result
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ValueError("Unclosed quote")
        return value[1:-1].replace("''", "'")
    if value.startswith("["):
        if not value.endswith("]"):
            raise ValueError("Unclosed list")
        inner = value[1:-1].strip()
        return [_scalar(item) for item in _split_list(inner)] if inner else []
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", value):
        return float(value)
    if value.startswith(("{", "|", ">")) or re.search(r":(?:\s|$)", value):
        raise ValueError("Unsupported scalar")
    return value


def _value(value: str, children: list[str]) -> object:
    value = _strip_comment(value.strip())
    if not children:
        return _scalar(value)
    if value:
        raise ValueError("Unexpected continuation")
    indentation = len(children[0]) - len(children[0].lstrip(" "))
    items: list[object] = []
    for child in children:
        if "\t" in child[:len(child) - len(child.lstrip())]:
            raise ValueError("Tab indentation")
        if len(child) - len(child.lstrip(" ")) != indentation:
            raise ValueError("Inconsistent list indentation")
        item = child[indentation:]
        if item != "-" and not item.startswith("- "):
            raise ValueError("Expected a list item")
        items.append(_scalar(item[1:].lstrip()))
    return items


def _yaml(block: str) -> tuple[dict[str, object], str | None]:
    lines = block.splitlines()
    meta: dict[str, object] = {}
    partial = False
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace() or re.match(r"^-(?:\s|$)", line) or ":" not in line:
            raise ValueError("Expected a top-level key")
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise ValueError("Empty key")
        children: list[str] = []
        while index < len(lines):
            child = lines[index]
            if not child.strip() or child.lstrip().startswith("#"):
                index += 1
                continue
            if not child[0].isspace() and not re.match(r"^-(?:\s|$)", child):
                break
            children.append(child)
            index += 1
        try:
            meta[key] = _value(value, children)
        except (ValueError, RecursionError):
            meta.pop(key, None)
            partial = True
    warning = "frontmatter_partial" if partial else None
    return meta, warning


def declares_private(text: str) -> bool:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0] != "---":
        return False
    closing = next((index for index in range(1, len(lines)) if lines[index] == "---"), None)
    end = closing if closing is not None else 200
    declaration = re.compile(
        r'''(?:^|[{,])\s*(?:"visibility"|'visibility'|visibility)\s*:\s*'''
        r'''["']?private\b''',
        re.IGNORECASE,
    )
    return any(declaration.search(line) is not None for line in lines[1:end])


def parse_frontmatter(text: str) -> tuple[dict, str, str | None]:
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}, text, None
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip("\r\n") == "---"),
        None,
    )
    if closing is None:
        return {}, text, "frontmatter_unclosed"
    block = "".join(lines[1:closing])
    try:
        if block.lstrip().startswith("{"):
            meta = json.loads(block)
            if not isinstance(meta, dict):
                raise ValueError("Expected a JSON object")
            warning = None
        else:
            meta, warning = _yaml(block)
    except (ValueError, RecursionError):
        return {}, text, "frontmatter_invalid"
    return meta, "".join(lines[closing + 1:]), warning
