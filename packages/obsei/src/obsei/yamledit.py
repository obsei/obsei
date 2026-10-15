"""Minimal text edits to ``obsei.yaml`` that keep its comments and layout: PyYAML only reads
positions here, and new entries are inserted as text."""

from __future__ import annotations

import json
from collections.abc import Callable

import yaml
from pydantic import JsonValue
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

Locate = Callable[[MappingNode], MappingNode]


class EditError(ValueError):
    pass


class _Dumper(yaml.SafeDumper):
    pass


def _list(dumper: yaml.SafeDumper, data: list[JsonValue]) -> yaml.Node:
    flow = all(not isinstance(v, dict | list) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_Dumper.add_representer(list, _list)


def _value(mapping: MappingNode, key: str) -> Node | None:
    return next((v for k, v in mapping.value if k.value == key), None)


def root(node: MappingNode) -> MappingNode:
    return node


def pipeline(name: str) -> Locate:
    def locate(node: MappingNode) -> MappingNode:
        pipelines = _value(node, "pipelines")
        items: list[Node] = pipelines.value if isinstance(pipelines, SequenceNode) else []
        for item in items:
            if not isinstance(item, MappingNode):
                continue
            named = _value(item, "name")
            if isinstance(named, ScalarNode) and named.value == name:
                return item
        raise EditError(f"no pipeline named {name!r}")

    return locate


def child(key: str) -> Locate:
    def locate(node: MappingNode) -> MappingNode:
        found = _value(node, key)
        if not isinstance(found, MappingNode):
            raise EditError(f"{key} is not a mapping")
        return found

    return locate


def _mapping(text: str, locate: Locate) -> MappingNode:
    node = yaml.compose(text)
    if not isinstance(node, MappingNode):
        raise EditError("obsei.yaml is not a mapping")
    return locate(node)


def _line_end(text: str, index: int) -> int:
    """Where the next line starts after ``index``, past any comment on its line."""
    if index > 0 and text[index - 1] == "\n":
        return index
    newline = text.find("\n", index)
    return len(text) if newline < 0 else newline + 1


def _content_end(node: Node) -> int:
    """Block collections end where the next token starts, often after comments; this is the end
    of their last value instead."""
    while isinstance(node, MappingNode | SequenceNode) and not node.flow_style and node.value:
        last = node.value[-1]
        node = last[1] if isinstance(node, MappingNode) else last
    return node.end_mark.index


def _insert(text: str, at: int, block: str) -> str:
    prefix = "\n" if at == len(text) and text and not text.endswith("\n") else ""
    return text[:at] + prefix + block + text[at:]


def _indent(block: str, pad: str) -> str:
    return "".join(f"{pad}{line}\n" for line in block.splitlines())


def _item(item: JsonValue, column: int) -> str:
    if not isinstance(item, dict):
        return f"{' ' * column}- {json.dumps(item)}\n"
    body = yaml.dump(item, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)
    first, *rest = body.splitlines()
    return f"{' ' * column}- {first}\n" + _indent("\n".join(rest), " " * (column + 2))


def _key_column(mapping: MappingNode) -> int:
    return mapping.value[0][0].start_mark.column if mapping.value else 0


def append(text: str, locate: Locate, key: str, item: JsonValue) -> str:
    """Add ``item`` to the list under ``key`` of the located mapping, creating the key."""
    mapping = _mapping(text, locate)
    value = _value(mapping, key)
    if isinstance(value, SequenceNode) and value.flow_style:
        close = value.end_mark.index - 1
        separator = ", " if value.value else ""
        return text[:close] + separator + json.dumps(item) + text[close:]
    if isinstance(value, SequenceNode) and value.value:
        at = _line_end(text, _content_end(value))
        return _insert(text, at, _item(item, value.start_mark.column))
    column = _key_column(mapping)
    if value is not None:
        if not (isinstance(value, ScalarNode) and value.tag.endswith(":null")):
            raise EditError(f"{key} is not a list")
        key_node = next(k for k, v in mapping.value if v is value)
        at = _line_end(text, key_node.end_mark.index)
        return _insert(text, at, _item(item, column + 2))
    at = _line_end(text, _content_end(mapping))
    return _insert(text, at, f"{' ' * column}{key}:\n" + _item(item, column + 2))


def set_scalar(text: str, locate: Locate, key: str, value: str) -> str:
    """Set ``key`` of the located mapping to a plain scalar, adding the key when missing."""
    mapping = _mapping(text, locate)
    node = _value(mapping, key)
    if isinstance(node, ScalarNode) and not node.tag.endswith(":null"):
        return text[: node.start_mark.index] + value + text[node.end_mark.index :]
    if node is not None:
        raise EditError(f"{key} is not a scalar")
    at = _line_end(text, _content_end(mapping))
    return _insert(text, at, f"{' ' * _key_column(mapping)}{key}: {value}\n")


def add_mapping(text: str, key: str, value: dict[str, JsonValue]) -> str:
    """Add a top-level ``key`` holding ``value``."""
    mapping = _mapping(text, root)
    if _value(mapping, key) is not None:
        raise EditError(f"{key} is already set")
    body = yaml.dump({key: value}, Dumper=_Dumper, sort_keys=False, allow_unicode=True)
    return _insert(text, _line_end(text, _content_end(mapping)), body)
