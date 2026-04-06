from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ast import Document, Node, TextOrNode


class ParseError(ValueError):
    def __init__(self, message: str, source: str, position: int) -> None:
        self.message = message
        self.source = source
        self.position = max(0, min(position, len(source)))
        self.line, self.column = _line_and_column(source, self.position)
        self.snippet = _line_text(source, self.position)
        super().__init__(self.__str__())

    def __str__(self) -> str:
        caret = " " * (self.column - 1) + "^"
        return f"{self.message} at line {self.line}, column {self.column}\n{self.snippet}\n{caret}"


def parse(source: str) -> Document:
    parser = _Parser(source)
    return parser.parse_document()


@dataclass
class _Parser:
    source: str
    position: int = 0

    def parse_document(self) -> Document:
        return Document(nodes=_apply_paragraphs(self._parse_children(stop_char=None)))

    def _parse_children(self, stop_char: str | None) -> list[TextOrNode]:
        children: list[TextOrNode] = []
        text_parts: list[str] = []

        while not self._at_end():
            if stop_char is not None and self._peek() == stop_char:
                break
            if self._starts_with("\\{") or self._starts_with("\\}"):
                text_parts.append(self.source[self.position + 1])
                self.position += 2
                continue
            if self._starts_with("```"):
                self._flush_text(text_parts, children)
                children.append(self._parse_raw_text())
                continue
            if self._peek() == "{":
                self._flush_text(text_parts, children)
                children.append(self._parse_node())
                continue
            if self._peek() == "#":
                self._consume_comment()
                continue
            text_parts.append(self._advance())

        self._flush_text(text_parts, children)
        return children

    def _parse_node(self) -> Node:
        self._expect("{")
        self._consume_whitespace()
        tag = self._parse_tag()
        self._consume_whitespace()

        attributes = None
        if self._peek() == "`" and not self._starts_with("```"):
            attributes = self._parse_attributes()
            self._consume_whitespace()

        children = self._parse_children(stop_char="}")
        if self._at_end():
            self._error("Unterminated node; missing '}'")
        self._expect("}")
        return Node(tag=tag, attributes=attributes, children=children)

    def _parse_tag(self) -> str:
        start = self.position
        while not self._at_end() and self._peek() not in " \t\r\n}`":
            self.position += 1
        if self.position == start:
            self._error("Expected tag name", position=start)
        return self.source[start:self.position]

    def _parse_attributes(self) -> Any:
        self._expect("`")
        start = self.position
        while not self._at_end() and self._peek() != "`":
            self.position += 1
        if self._at_end():
            self._error("Unterminated attribute block", position=start - 1)
        raw = self.source[start:self.position]
        self._expect("`")
        return _parse_attribute_value(raw.strip(), self.source, start)

    def _parse_raw_text(self) -> str:
        self._expect("```")
        start = self.position
        end = self.source.find("```", self.position)
        if end == -1:
            self._error("Unterminated raw text block", position=start - 3)
        self.position = end
        raw = self.source[start:end]
        self._expect("```")
        return raw

    def _consume_comment(self) -> None:
        while not self._at_end() and self._peek() != "\n":
            self.position += 1

    def _consume_whitespace(self) -> None:
        while not self._at_end() and self._peek().isspace():
            self.position += 1

    def _flush_text(self, text_parts: list[str], children: list[TextOrNode]) -> None:
        if text_parts:
            children.extend(_parse_inline_text("".join(text_parts)))
            text_parts.clear()

    def _peek(self) -> str:
        return self.source[self.position]

    def _starts_with(self, prefix: str) -> bool:
        return self.source.startswith(prefix, self.position)

    def _advance(self) -> str:
        char = self.source[self.position]
        self.position += 1
        return char

    def _expect(self, token: str) -> None:
        if not self._starts_with(token):
            self._error(f"Expected {token!r}")
        self.position += len(token)

    def _at_end(self) -> bool:
        return self.position >= len(self.source)

    def _error(self, message: str, position: int | None = None) -> None:
        raise ParseError(message, self.source, self.position if position is None else position)


def _parse_attribute_value(raw: str, source: str, position: int) -> Any:
    if not raw:
        return ""
    if raw.startswith("{") or raw.startswith("[") or raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON attributes: {exc.msg}", source, position + exc.pos) from exc

    parts = raw.split()
    if len(parts) == 1 and "=" not in parts[0]:
        return parts[0]

    attributes: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            raise ParseError(f"Invalid shorthand attribute token: {part!r}", source, position)
        key, value = part.split("=", 1)
        if not key:
            raise ParseError("Attribute keys must not be empty", source, position)
        attributes[key] = value
    return attributes


def _line_and_column(source: str, position: int) -> tuple[int, int]:
    line = source.count("\n", 0, position) + 1
    line_start = source.rfind("\n", 0, position) + 1
    column = position - line_start + 1
    return line, column


def _line_text(source: str, position: int) -> str:
    line_start = source.rfind("\n", 0, position) + 1
    line_end = source.find("\n", position)
    if line_end == -1:
        line_end = len(source)
    return source[line_start:line_end]


def _parse_inline_text(text: str) -> list[TextOrNode]:
    result: list[TextOrNode] = []
    index = 0
    plain_start = 0

    while index < len(text):
        marker = None
        tag = None
        if text.startswith("**", index):
            marker = "**"
            tag = "strong"
        elif text[index] == "*":
            marker = "*"
            tag = "em"

        if marker is None:
            index += 1
            continue

        close = text.find(marker, index + len(marker))
        if close == -1 or close == index + len(marker):
            index += len(marker)
            continue

        if plain_start < index:
            result.append(text[plain_start:index])
        inner = text[index + len(marker) : close]
        result.append(Node(tag=tag, children=_parse_inline_text(inner)))
        index = close + len(marker)
        plain_start = index

    if plain_start < len(text):
        result.append(text[plain_start:])
    return [item for item in result if not (isinstance(item, str) and item == "")]


def _apply_paragraphs(children: list[TextOrNode]) -> list[TextOrNode]:
    result: list[TextOrNode] = []
    current: list[TextOrNode] = []
    paragraph_break_tags = {"sec", "sec-push", "sec-pop", "p"}
    inline_tags = {"em", "strong"}

    for child in children:
        if isinstance(child, str):
            segments = _split_paragraph_text(child)
            for is_break, value in segments:
                if is_break:
                    _flush_paragraph(current, result)
                elif value:
                    current.append(value)
            continue

        if child.tag in paragraph_break_tags:
            _flush_paragraph(current, result)
            result.append(child)
            continue

        if current or child.tag in inline_tags:
            current.append(child)
        else:
            result.append(child)

    _flush_paragraph(current, result)
    return result


def _split_paragraph_text(text: str) -> list[tuple[bool, str]]:
    parts: list[tuple[bool, str]] = []
    start = 0
    index = 0

    while index < len(text):
        if text[index] == "\n":
            end = index + 1
            while end < len(text) and text[end] in " \t\r":
                end += 1
            if end < len(text) and text[end] == "\n":
                parts.append((False, text[start:index]))
                while end < len(text) and text[end] == "\n":
                    end += 1
                    while end < len(text) and text[end] in " \t\r":
                        end += 1
                parts.append((True, ""))
                start = end
                index = end
                continue
        index += 1

    parts.append((False, text[start:]))
    return parts


def _flush_paragraph(current: list[TextOrNode], result: list[TextOrNode]) -> None:
    if not current:
        return
    normalized = _trim_paragraph_edges(current)
    current.clear()
    if not normalized:
        return
    result.append(Node(tag="p", children=normalized))


def _trim_paragraph_edges(children: list[TextOrNode]) -> list[TextOrNode]:
    trimmed = list(children)
    while trimmed and isinstance(trimmed[0], str):
        updated = trimmed[0].lstrip()
        if updated:
            trimmed[0] = updated
            break
        trimmed.pop(0)
    while trimmed and isinstance(trimmed[-1], str):
        updated = trimmed[-1].rstrip()
        if updated:
            trimmed[-1] = updated
            break
        trimmed.pop()
    return trimmed
