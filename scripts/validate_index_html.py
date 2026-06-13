#!/usr/bin/env python3
"""
Validate the generated index.html structure for basic deployment sanity.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.title_text: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}>")
            return
        last = self.stack.pop()
        if last != tag:
            self.errors.append(f"Mismatched closing tag </{tag}>; expected </{last}>")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text.append(data)


def emit_error(message: str) -> None:
    safe = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    target_name = CURRENT_TARGET.name if CURRENT_TARGET else "index.html"
    print(f"::error file={target_name},title=HTML Guard::{safe}")


CURRENT_TARGET: Path | None = None


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("index.html")
    global CURRENT_TARGET
    CURRENT_TARGET = target
    if not target.exists():
        emit_error(f"{target} does not exist")
        return 1

    html = target.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []

    if not html.lstrip().lower().startswith("<!doctype html>"):
        failures.append("Missing <!DOCTYPE html> declaration at the top of index.html")

    for token in ("<html", "<head", "<body", "</html>"):
        if token not in html.lower():
            failures.append(f"Missing required HTML token: {token}")

    parser = StructureParser()
    parser.feed(html)
    parser.close()

    failures.extend(parser.errors)

    title = "".join(parser.title_text).strip()
    if not title:
        failures.append("HTML title must not be empty")

    if "<style" not in html.lower():
        failures.append("Expected an inline <style> block")
    if "<script" not in html.lower():
        failures.append("Expected an inline <script> block")

    stage_matches = re.findall(r'id="stage-\d+"', html)
    is_tabbed_hub = 'id="page-frame"' in html and "data-page=" in html
    if not stage_matches and not is_tabbed_hub:
        failures.append("Expected either at least one stage section or a tabbed page hub frame")

    if failures:
        for failure in failures:
            emit_error(failure)
        print(f"HTML validation failed with {len(failures)} error(s).")
        return 1

    print(f"HTML validation passed for {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
