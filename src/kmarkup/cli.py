from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parser import ParseError, parse
from .postsyntax import PostSyntaxError
from .renderers import render_html_document, to_json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kmarkup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="Convert kmarkup input to another format.")
    convert.add_argument("infile", nargs="?")
    convert.add_argument("outfile")
    convert.add_argument("--format", choices=("html", "json"))
    convert.add_argument("--input", dest="input_text")
    convert.add_argument("--css")
    convert.add_argument("--template",
                         choices=("basic", "default", "none"),
                         default="default")

    args = parser.parse_args(argv)
    if args.command == "convert":
        try:
            _run_convert_command(args, parser)
        except (ParseError, PostSyntaxError) as exc:
            sys.stderr.write(f"kmarkup: {exc}\n")
            raise SystemExit(1) from exc


def _run_convert_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.input_text is not None and args.infile is not None:
        parser.error("Use either INFILE or --input, not both.")
    if args.input_text is None and args.infile is None:
        parser.error("INFILE is required unless --input is provided.")
    if args.outfile == "-" and args.format is None:
        parser.error("--format is required when OUTFILE is '-'.")

    output_format = _resolve_format(args.outfile, args.format)
    if args.css is not None and output_format != "html":
        parser.error("--css can only be used with HTML output.")
    if args.template != "none" and output_format != "html":
        parser.error("--template can only be used with HTML output.")

    source = args.input_text
    if source is None:
        source = Path(args.infile).read_text()

    css_text = Path(args.css).read_text() if args.css is not None else None
    rendered = _render_output(source, output_format, css_text=css_text, template_name=args.template)
    if args.outfile == "-":
        sys.stdout.write(rendered + "\n")
    else:
        Path(args.outfile).write_text(rendered + "\n")


def _convert(
    infile: Path,
    outfile: Path,
    output_format: str | None = None,
    css_file: Path | None = None,
    template_name: str = "none",
) -> None:
    resolved_format = _resolve_format(str(outfile), output_format)
    if css_file is not None and resolved_format != "html":
        raise SystemExit("--css can only be used with HTML output.")
    if template_name != "none" and resolved_format != "html":
        raise SystemExit("--template can only be used with HTML output.")
    css_text = css_file.read_text() if css_file is not None else None
    rendered = _render_output(infile.read_text(), resolved_format, css_text=css_text, template_name=template_name)
    outfile.write_text(rendered + "\n")


def _render_output(
    source: str,
    output_format: str,
    css_text: str | None = None,
    template_name: str = "none",
) -> str:
    document = parse(source)
    if output_format == "json":
        rendered = to_json(document)
    elif output_format == "html":
        rendered = render_html_document(document, template_name=template_name, css_text=css_text)
    else:
        raise SystemExit(f"Unsupported output format: {output_format}")
    return rendered


def _resolve_format(outfile: str, output_format: str | None) -> str:
    if output_format is not None:
        return output_format

    suffix = Path(outfile).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".html":
        return "html"
    raise SystemExit(f"Unsupported output extension: {suffix}")
