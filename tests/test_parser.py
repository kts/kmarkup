from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kmarkup import PostSyntaxError, apply_post_syntax, parse
from kmarkup.cli import _convert, main
from kmarkup.parser import ParseError
from kmarkup.renderers import render_html_document, to_html


class ParserTests(unittest.TestCase):
    def test_readme_examples(self) -> None:
        triples = [
            (
                "basic",
                "{x y}",
                {"nodes": [{"tag": "x", "children": ["y"]}]},
            ),
            (
                "sentence",
                "{x A full sentence.}",
                {"nodes": [{"tag": "x", "children": ["A full sentence."]}]},
            ),
            (
                "nested",
                "{x A full {foo sentence}.}",
                {
                    "nodes": [
                        {
                            "tag": "x",
                            "children": [
                                "A full ",
                                {"tag": "foo", "children": ["sentence"]},
                                ".",
                            ],
                        }
                    ]
                },
            ),
        ]

        for _, source, expected in triples:
            with self.subTest(source=source):
                self.assertEqual(parse(source).to_dict(), expected)

    def test_attribute_forms(self) -> None:
        self.assertEqual(
            parse('{a `{"href":"/ok"}` link}').to_dict(),
            {"nodes": [{"tag": "a", "attributes": {"href": "/ok"}, "children": ["link"]}]},
        )
        self.assertEqual(
            parse("{foo `x=5 y=okay`}").to_dict(),
            {"nodes": [{"tag": "foo", "attributes": {"x": "5", "y": "okay"}, "children": []}]},
        )
        self.assertEqual(
            parse("{foo `xyz`}").to_dict(),
            {"nodes": [{"tag": "foo", "attributes": "xyz", "children": []}]},
        )

    def test_comments_are_ignored_until_newline(self) -> None:
        document = parse("before # comment\n{x y}")
        self.assertEqual(
            document.to_dict(),
            {"nodes": [{"tag": "p", "children": ["before \n", {"tag": "x", "children": ["y"]}]}]},
        )

    def test_raw_text_preserves_markup_characters(self) -> None:
        document = parse("{div ```\n#not a comment\n{ } } }\n```}")
        self.assertEqual(
            document.to_dict(),
            {"nodes": [{"tag": "div", "children": ["\n#not a comment\n{ } } }\n"]}]},
        )

    def test_escaped_braces_are_literal_text(self) -> None:
        document = parse(r"before \{ middle \} after")
        self.assertEqual(document.to_dict(), {"nodes": [{"tag": "p", "children": ["before { middle } after"]}]})

    def test_escaped_braces_work_inside_nodes(self) -> None:
        document = parse(r"{p \{hello\}}")
        self.assertEqual(document.to_dict(), {"nodes": [{"tag": "p", "children": ["{hello}"]}]})

    def test_unterminated_node_raises(self) -> None:
        with self.assertRaises(ParseError) as exc:
            parse("{x y")

        self.assertIn("line 1, column 5", str(exc.exception))
        self.assertIn("{x y", str(exc.exception))
        self.assertIn("^", str(exc.exception))

    def test_parse_error_reports_line_and_snippet(self) -> None:
        source = "before\n{ }"
        with self.assertRaises(ParseError) as exc:
            parse(source)

        rendered = str(exc.exception)
        self.assertIn("Expected tag name at line 2, column 3", rendered)
        self.assertIn("{ }", rendered)
        self.assertIn("  ^", rendered)

    def test_blank_lines_create_top_level_paragraphs(self) -> None:
        document = parse("p1\n\np2")
        self.assertEqual(
            document.to_dict(),
            {
                "nodes": [
                    {"tag": "p", "children": ["p1"]},
                    {"tag": "p", "children": ["p2"]},
                ]
            },
        )

    def test_emphasis_creates_inline_nodes(self) -> None:
        document = parse("*abc* **xyz**")
        self.assertEqual(
            document.to_dict(),
            {
                "nodes": [
                    {"tag": "p", "children": [
                        {"tag": "em", "children": ["abc"]},
                        " ",
                        {"tag": "strong", "children": ["xyz"]},
                    ]}
                ]
            },
        )

    def test_emphasis_inside_node_text(self) -> None:
        document = parse("{p hello *there*}")
        self.assertEqual(
            document.to_dict(),
            {
                "nodes": [
                    {"tag": "p", "children": ["hello ", {"tag": "em", "children": ["there"]}]}
                ]
            },
        )


class RenderTests(unittest.TestCase):
    def test_to_html(self) -> None:
        html = to_html(parse('{a `{"href":"/ok"}` link}'))
        self.assertEqual(html, '<!-- generated by kmarkup -->\n<a href="/ok">link</a>')

    def test_sections_render_as_html_sections(self) -> None:
        html = to_html(parse("{sec Title}ok"))
        self.assertEqual(html, "<!-- generated by kmarkup -->\n<section><h1>Title</h1><p>ok</p></section>")

    def test_nested_sections_follow_push_and_pop(self) -> None:
        source = "{sec Title}{sec-push}{sec Okay}{sec Foo}{sec-push}{sec Bar}{sec-pop}{sec Last}"
        html = to_html(parse(source))
        self.assertEqual(
            html,
            (
                "<!-- generated by kmarkup -->\n"
                "<section><h1>Title</h1>"
                "<section><h2>Okay</h2></section>"
                "<section><h2>Foo</h2><section><h3>Bar</h3></section></section>"
                "<section><h2>Last</h2></section>"
                "</section>"
            ),
        )

    def test_convert_json_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            infile.write_text("{b hi}")

            json_out = tmpdir / "out.json"
            html_out = tmpdir / "out.html"

            _convert(infile, json_out)
            _convert(infile, html_out)

            self.assertEqual(json.loads(json_out.read_text()), {"nodes": [{"tag": "b", "children": ["hi"]}]})
            self.assertEqual(html_out.read_text(), "<!-- generated by kmarkup -->\n<b>hi</b>\n")

    def test_convert_respects_explicit_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            outfile = tmpdir / "out.data"

            infile.write_text("{b hi}")
            _convert(infile, outfile, output_format="json")

            self.assertEqual(json.loads(outfile.read_text()), {"nodes": [{"tag": "b", "children": ["hi"]}]})

    def test_convert_inlines_css_for_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            outfile = tmpdir / "out.html"
            css_file = tmpdir / "style.css"

            infile.write_text("{b hi}")
            css_file.write_text("body { color: red; }")
            _convert(infile, outfile, css_file=css_file)

            self.assertEqual(
                outfile.read_text(),
                "<style>\nbody { color: red; }\n</style>\n<!-- generated by kmarkup -->\n<b>hi</b>\n",
            )

    def test_convert_wraps_html_in_basic_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            outfile = tmpdir / "out.html"

            infile.write_text("{b hi}")
            _convert(infile, outfile, template_name="basic")

            rendered = outfile.read_text()
            self.assertTrue(rendered.startswith("<!DOCTYPE html>\n<!-- generated by kmarkup -->\n<html lang=\"en\">"))
            self.assertIn("<main>\n<!-- generated by kmarkup -->\n<b>hi</b>\n  </main>", rendered)
            self.assertIn("font-family: Georgia", rendered)

    def test_convert_merges_css_into_basic_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            outfile = tmpdir / "out.html"
            css_file = tmpdir / "style.css"

            infile.write_text("{b hi}")
            css_file.write_text("b { color: red; }")
            _convert(infile, outfile, css_file=css_file, template_name="basic")

            rendered = outfile.read_text()
            self.assertIn("font-family: Georgia", rendered)
            self.assertIn("b { color: red; }", rendered)

    def test_default_template_adds_toc_and_section_anchors(self) -> None:
        rendered = render_html_document(
            parse("{sec Main}{sec-push}{sec Child}{sec-pop}{sec Next}"),
            template_name="default",
        )
        self.assertTrue(rendered.startswith("<!DOCTYPE html>\n<!-- generated by kmarkup -->\n<html lang=\"en\">"))
        self.assertIn('<aside class="toc">', rendered)
        self.assertIn('<a href="#sec-1">Main</a>', rendered)
        self.assertIn('<a href="#sec-1-1">Child</a>', rendered)
        self.assertIn('<section id="sec-1">', rendered)
        self.assertIn('@media (max-width: 860px)', rendered)

    def test_default_template_merges_custom_css(self) -> None:
        rendered = render_html_document(parse("{sec Main}"), template_name="default", css_text="main { color: red; }")
        self.assertIn("main { color: red; }", rendered)

    def test_post_syntax_preserves_raw_json_ast(self) -> None:
        document = parse("{sec Title}")
        self.assertEqual(document.to_dict(), {"nodes": [{"tag": "sec", "children": ["Title"]}]})
        self.assertEqual(
            apply_post_syntax(document).to_dict(),
            {"nodes": [{"tag": "section", "children": [{"tag": "h1", "children": ["Title"]}]}]},
        )

    def test_sec_pop_without_push_raises(self) -> None:
        with self.assertRaises(PostSyntaxError):
            to_html(parse("{sec Title}{sec-pop}"))

    def test_sec_push_without_open_section_raises(self) -> None:
        with self.assertRaises(PostSyntaxError):
            to_html(parse("{sec-push}{sec Title}"))


class CliTests(unittest.TestCase):
    def test_main_accepts_input_string_and_stdout(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main(["convert", "--input", "{b hi}", "-", "--format", "html"])

        self.assertEqual(buffer.getvalue(), "<!-- generated by kmarkup -->\n<b>hi</b>\n")

    def test_main_resolves_format_from_outfile_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            outfile = tmpdir / "out.json"

            main(["convert", "--input", "{b hi}", str(outfile)])

            self.assertEqual(json.loads(outfile.read_text()), {"nodes": [{"tag": "b", "children": ["hi"]}]})

    def test_stdout_requires_explicit_format(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            main(["convert", "--input", "{b hi}", "-"])

        self.assertEqual(exc.exception.code, 2)

    def test_infile_and_input_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            infile = tmpdir / "input.km"
            infile.write_text("{b hi}")

            with self.assertRaises(SystemExit) as exc:
                main(["convert", str(infile), str(tmpdir / "out.html"), "--input", "{i no}"])

        self.assertEqual(exc.exception.code, 2)

    def test_css_argument_is_applied_to_html_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            css_file = tmpdir / "style.css"
            css_file.write_text("p { font-weight: bold; }")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                main(["convert", "--input", "{p hi}", "-", "--format", "html", "--css", str(css_file)])

        self.assertEqual(
            buffer.getvalue(),
            "<style>\np { font-weight: bold; }\n</style>\n<!-- generated by kmarkup -->\n<p>hi</p>\n",
        )

    def test_css_argument_is_rejected_for_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            css_file = tmpdir / "style.css"
            css_file.write_text("body { color: red; }")

            with self.assertRaises(SystemExit) as exc:
                main(["convert", "--input", "{b hi}", "-", "--format", "json", "--css", str(css_file)])

        self.assertEqual(exc.exception.code, 2)

    def test_basic_template_is_applied_to_html_stdout(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main(["convert", "--input", "{b hi}", "-", "--format", "html", "--template", "basic"])

        rendered = buffer.getvalue()
        self.assertTrue(rendered.startswith("<!DOCTYPE html>\n<!-- generated by kmarkup -->\n<html lang=\"en\">"))
        self.assertIn("<main>\n<!-- generated by kmarkup -->\n<b>hi</b>\n  </main>", rendered)

    def test_default_template_is_applied_to_html_stdout(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main(["convert", "--input", "{sec Main}{sec-push}{sec Child}", "-", "--format", "html", "--template", "default"])

        rendered = buffer.getvalue()
        self.assertIn('<aside class="toc">', rendered)
        self.assertIn('<a href="#sec-1">Main</a>', rendered)
        self.assertIn('<a href="#sec-1-1">Child</a>', rendered)

    def test_template_argument_is_rejected_for_json(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            main(["convert", "--input", "{b hi}", "-", "--format", "json", "--template", "basic"])

        self.assertEqual(exc.exception.code, 2)

    def test_main_reports_parse_errors_cleanly(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as exc:
                main(["convert", "--input", "{ }", "-", "--format", "json"])

        self.assertEqual(exc.exception.code, 1)
        rendered = stderr.getvalue()
        self.assertIn("kmarkup: Expected tag name at line 1, column 3", rendered)
        self.assertIn("{ }", rendered)
        self.assertIn("^", rendered)


if __name__ == "__main__":
    unittest.main()
