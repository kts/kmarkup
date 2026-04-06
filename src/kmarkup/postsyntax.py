from __future__ import annotations

from dataclasses import replace

from .ast import Document, Node, TextOrNode


class PostSyntaxError(ValueError):
    pass


def apply_post_syntax(document: Document) -> Document:
    return Document(nodes=_transform_children(document.nodes))


def _transform_children(children: list[TextOrNode]) -> list[TextOrNode]:
    result: list[TextOrNode] = []
    section_stack: list[Node] = []
    section_parent_depth = -1

    for child in children:
        if isinstance(child, str):
            _current_container(result, section_stack).append(child)
            continue

        if child.tag == "sec":
            parent = _parent_for_depth(result, section_stack, section_parent_depth)
            section = Node(
                tag="section",
                attributes=child.attributes,
                children=[Node(tag=_heading_tag(section_parent_depth + 2), children=_transform_children(child.children))],
            )
            parent.append(section)
            section_stack = section_stack[: section_parent_depth + 1]
            section_stack.append(section)
            continue

        if child.tag == "sec-push":
            if not section_stack:
                raise PostSyntaxError("{sec-push} requires an open section")
            section_parent_depth = len(section_stack) - 1
            continue

        if child.tag == "sec-pop":
            if section_parent_depth < 0:
                raise PostSyntaxError("{sec-pop} has no matching {sec-push}")
            section_parent_depth -= 1
            section_stack = section_stack[: section_parent_depth + 1]
            continue

        transformed = replace(child, children=_transform_children(child.children))
        _current_container(result, section_stack).append(transformed)

    return result


def _current_container(result: list[TextOrNode], section_stack: list[Node]) -> list[TextOrNode]:
    if section_stack:
        return section_stack[-1].children
    return result


def _parent_for_depth(result: list[TextOrNode], section_stack: list[Node], section_parent_depth: int) -> list[TextOrNode]:
    if section_parent_depth >= 0:
        return section_stack[section_parent_depth].children
    return result


def _heading_tag(level: int) -> str:
    return f"h{min(level, 6)}"
