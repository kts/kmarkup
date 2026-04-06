from __future__ import annotations

import html
import json
from typing import Any

from .ast import Document, Node, TextOrNode
from .postsyntax import apply_post_syntax


def to_json(document: Document) -> str:
    return json.dumps(document.to_dict(), indent=2)


def to_html(document: Document) -> str:
    transformed = apply_post_syntax(document)
    return render_html_fragment(transformed)


def render_html_document(document: Document, template_name: str = "none", css_text: str | None = None) -> str:
    transformed = apply_post_syntax(document)
    if template_name == "none":
        html_output = render_html_fragment(transformed)
        if css_text is not None:
            return with_inline_css(html_output, css_text)
        return html_output
    if template_name == "basic":
        html_output = render_html_fragment(transformed)
        return with_basic_template(html_output, css_text=css_text)
    if template_name == "default":
        _collect_section_entries(transformed.nodes)
        html_output = render_html_fragment(transformed)
        return with_default_template(transformed, html_output, css_text=css_text)
    raise SystemExit(f"Unsupported template: {template_name}")


def render_html_fragment(document: Document) -> str:
    return _generated_comment() + "".join(_render_html(child) for child in document.nodes)


def with_inline_css(html_output: str, css_text: str) -> str:
    return f"<style>\n{css_text}\n</style>\n{html_output}"


def with_basic_template(html_output: str, css_text: str | None = None) -> str:
    base_css = """
:root {
  color-scheme: light;
}

body {
  margin: 0;
  font-family: Georgia, "Times New Roman", serif;
  background: #f6f4ee;
  color: #1f1d1a;
}

main {
  max-width: 46rem;
  margin: 0 auto;
  padding: 3rem 1.5rem 4rem;
  line-height: 1.7;
}

section {
  margin: 0 0 2rem;
}

h1, h2, h3, h4, h5, h6 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.2;
  margin: 0 0 0.75rem;
}

p {
  margin: 0 0 1rem;
}

a {
  color: #0a5c8f;
}
""".strip()
    style_text = base_css if css_text is None else f"{base_css}\n\n{css_text}"
    return (
        "<!DOCTYPE html>\n"
        f"{_generated_comment()}"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>kmarkup</title>\n"
        "  <style>\n"
        f"{style_text}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"{html_output}\n"
        "  </main>\n"
        "</body>\n"
        "</html>"
    )


def with_default_template(document: Document, html_output: str, css_text: str | None = None) -> str:
    toc = _build_toc(document)
    base_css = """
:root {
  color-scheme: light;
  --bg: #f6f4ee;
  --panel: #ebe6d8;
  --ink: #1f1d1a;
  --muted: #6a655d;
  --accent: #0a5c8f;
  --border: #d7cfbe;
}

* {
  box-sizing: border-box;
}


/* temp? */
td,th {
 border:1px solid #ccf;
    }
    
    
    
body {
  margin: 0;
  font-family: Georgia, "Times New Roman", serif;
  background: var(--bg);
  color: var(--ink);


  font-size: 120%; /* ? */    
}

.layout {
  display: grid;
  grid-template-columns: minmax(14rem, 18rem) minmax(0, 1fr);
  min-height: 100vh;
}

.toc {
  position: sticky;
  top: 0;
  align-self: start;
  height: 100vh;
  overflow-y: auto;
  padding: 2rem 1.25rem;
  background: var(--panel);
  border-right: 1px solid var(--border);
}

.toc h1 {
  margin: 0 0 1rem;
  font: 600 0.95rem/1.2 "Helvetica Neue", Helvetica, Arial, sans-serif;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.toc ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.toc li + li {
  margin-top: 0.45rem;
}

.toc a {
  color: var(--muted);
  text-decoration: none;
}

.toc a:hover {
  color: var(--accent);
}

.toc .toc-depth-2 {
  padding-left: 1rem;
}

.toc .toc-depth-3,
.toc .toc-depth-4,
.toc .toc-depth-5,
.toc .toc-depth-6 {
  padding-left: 2rem;
}

.content {
  min-width: 0;
  padding: 3rem 1.5rem 4rem;
}

main {
  max-width: 48rem;
  margin: 0 auto;
  line-height: 1.7;
}

section {
  margin: 0 0 2rem;
  scroll-margin-top: 1.5rem;
}

h1, h2, h3, h4, h5, h6 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.2;
  margin: 0 0 0.75rem;
}

p {
  margin: 0 0 1rem;
}

a {
  color: var(--accent);
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .toc {
    position: static;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .content {
    padding-top: 2rem;
  }
}
""".strip()
    style_text = base_css if css_text is None else f"{base_css}\n\n{css_text}"
    return (
        "<!DOCTYPE html>\n"
        f"{_generated_comment()}"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>kmarkup</title>\n"
        "  <style>\n"
        f"{style_text}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div class="layout">\n'
        '    <aside class="toc">\n'
        "      <h1>Contents</h1>\n"
        f"{toc}\n"
        "    </aside>\n"
        '    <div class="content">\n'
        "      <main>\n"
        f"{html_output}\n"
        "      </main>\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>"
    )


def _render_html(value: TextOrNode) -> str:
    if isinstance(value, str):
        return html.escape(value)

    attrs = _render_attributes(value.attributes)
    children = "".join(_render_html(child) for child in value.children)
    return f"<{value.tag}{attrs}>{children}</{value.tag}>"


def _render_attributes(attributes: Any) -> str:
    if attributes is None:
        return ""
    if isinstance(attributes, dict):
        pieces = [f' {key}="{html.escape(str(value), quote=True)}"' for key, value in attributes.items()]
        return "".join(pieces)
    return f' data-kmarkup-attributes="{html.escape(json.dumps(attributes), quote=True)}"'


def _generated_comment() -> str:
    return "<!-- generated by kmarkup -->\n"


def _build_toc(document: Document) -> str:
    entries = _collect_section_entries(document.nodes)
    if not entries:
        return "      <p>No sections</p>"
    items = [
        f'        <li class="toc-depth-{depth}"><a href="#{anchor}">{html.escape(title)}</a></li>'
        for depth, title, anchor in entries
    ]
    return "      <ul>\n" + "\n".join(items) + "\n      </ul>"


def _collect_section_entries(children: list[TextOrNode], counters: list[int] | None = None) -> list[tuple[int, str, str]]:
    if counters is None:
        counters = []
    entries: list[tuple[int, str, str]] = []
    section_index = 0

    for child in children:
        if not isinstance(child, Node) or child.tag != "section":
            continue

        section_index += 1
        local_counters = list(counters) + [section_index]
        heading = _find_heading(child)
        depth = 1
        title = "Untitled"
        if heading is not None:
            depth = _heading_level(heading.tag)
            title = _extract_text(heading.children).strip() or title
        anchor = "sec-" + "-".join(str(part) for part in local_counters)
        child.attributes = _merge_attributes(child.attributes, {"id": anchor})
        entries.append((depth, title, anchor))
        entries.extend(_collect_section_entries(child.children, local_counters))

    return entries


def _find_heading(section: Node) -> Node | None:
    for child in section.children:
        if isinstance(child, Node) and child.tag.startswith("h") and child.tag[1:].isdigit():
            return child
    return None


def _heading_level(tag: str) -> int:
    return max(1, min(int(tag[1:]), 6))


def _extract_text(children: list[TextOrNode]) -> str:
    parts: list[str] = []
    for child in children:
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(_extract_text(child.children))
    return "".join(parts)


def _merge_attributes(attributes: Any, additions: dict[str, str]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(attributes, dict):
        merged.update(attributes)
    elif attributes is not None:
        merged["data-kmarkup-attributes"] = json.dumps(attributes)
    merged.update(additions)
    return merged
