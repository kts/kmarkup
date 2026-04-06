from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union


@dataclass
class Node:
    tag: str
    attributes: Any = None
    children: list[TextOrNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"tag": self.tag, "children": _children_to_data(self.children)}
        if self.attributes is not None:
            data["attributes"] = self.attributes
        return data


@dataclass
class Document:
    nodes: list[TextOrNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": _children_to_data(self.nodes)}


TextOrNode = Union[str, Node]


def _children_to_data(children: list[TextOrNode]) -> list[Any]:
    result: list[Any] = []
    for child in children:
        if isinstance(child, Node):
            result.append(child.to_dict())
        else:
            result.append(child)
    return result
