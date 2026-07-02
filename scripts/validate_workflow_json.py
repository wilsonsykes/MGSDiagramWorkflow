#!/usr/bin/env python3
"""
Validate workflow JSON sources and emit GitHub Actions annotations for failures.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow_generate import load_json


PAGES_FILE = ROOT / "workflow_pages.json"
CONTROL_FILE = ROOT / "workflow_control.json"


@dataclass
class ValidationError:
    message: str
    file: Path
    line: int | None = None
    col: int | None = None


def _escape_annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit(error: ValidationError) -> None:
    msg = _escape_annotation(error.message)
    file_str = str(error.file).replace("\\", "/")
    if error.line is not None and error.col is not None:
        print(f"::error file={file_str},line={error.line},col={error.col},title=JSON Guard::{msg}")
        return
    if error.line is not None:
        print(f"::error file={file_str},line={error.line},title=JSON Guard::{msg}")
        return
    print(f"::error file={file_str},title=JSON Guard::{msg}")


def parse_with_location(path: Path, label: str) -> tuple[Any | None, list[ValidationError]]:
    errors: list[ValidationError] = []
    try:
        return load_json(path), errors
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        line = None
        col = None
        m = re.search(r"line (\d+) column (\d+)", text)
        if m:
            line = int(m.group(1))
            col = int(m.group(2))
        errors.append(ValidationError(f"{label} parse error: {text}", path, line, col))
        return None, errors


def expect_type(errors: list[ValidationError], value: Any, expected: type, path: str, file: Path) -> bool:
    if isinstance(value, expected):
        return True
    errors.append(ValidationError(f"{path} expected {expected.__name__}, got {type(value).__name__}", file))
    return False


def ensure_non_empty_str(errors: list[ValidationError], value: Any, path: str, file: Path) -> bool:
    if isinstance(value, str) and value.strip():
        return True
    errors.append(ValidationError(f"{path} must be a non-empty string", file))
    return False


VALID_BADGES = {"confirmed", "pending"}


def validate_approval_matrix_row(row: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, row, dict, path, file):
        return
    for key in ("transaction", "initiator", "reviewer", "approver"):
        ensure_non_empty_str(errors, row.get(key), f"{path}.{key}", file)
    if "controls" in row and expect_type(errors, row.get("controls"), list, f"{path}.controls", file):
        for i, c in enumerate(row["controls"]):
            ensure_non_empty_str(errors, c, f"{path}.controls[{i}]", file)


def validate_current_future(cf: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, cf, dict, path, file):
        return
    for key in ("current", "future"):
        if expect_type(errors, cf.get(key), list, f"{path}.{key}", file):
            if not cf[key]:
                errors.append(ValidationError(f"{path}.{key} must not be empty", file))
            for i, item in enumerate(cf[key]):
                ensure_non_empty_str(errors, item, f"{path}.{key}[{i}]", file)


def validate_stage(stage: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, stage, dict, path, file):
        return
    for key in ("romaji", "english"):
        ensure_non_empty_str(errors, stage.get(key), f"{path}.{key}", file)

    badge = stage.get("badge")
    if badge is not None and badge not in VALID_BADGES:
        errors.append(ValidationError(f"{path}.badge must be one of {sorted(VALID_BADGES)}, got {badge!r}", file))

    if expect_type(errors, stage.get("sop_steps"), list, f"{path}.sop_steps", file):
        if not stage["sop_steps"]:
            errors.append(ValidationError(f"{path}.sop_steps must not be empty", file))
        for i, step in enumerate(stage["sop_steps"]):
            ensure_non_empty_str(errors, step, f"{path}.sop_steps[{i}]", file)

    if expect_type(errors, stage.get("guidelines"), list, f"{path}.guidelines", file):
        if not stage["guidelines"]:
            errors.append(ValidationError(f"{path}.guidelines must not be empty", file))
        for i, item in enumerate(stage["guidelines"]):
            ensure_non_empty_str(errors, item, f"{path}.guidelines[{i}]", file)

    if expect_type(errors, stage.get("approval_matrix"), list, f"{path}.approval_matrix", file):
        if not stage["approval_matrix"]:
            errors.append(ValidationError(f"{path}.approval_matrix must not be empty", file))
        for i, row in enumerate(stage["approval_matrix"]):
            validate_approval_matrix_row(row, f"{path}.approval_matrix[{i}]", errors, file)

    validate_current_future(stage.get("current_future"), f"{path}.current_future", errors, file)

    if "gap_note" in stage:
        ensure_non_empty_str(errors, stage.get("gap_note"), f"{path}.gap_note", file)
    if "sources" in stage:
        ensure_non_empty_str(errors, stage.get("sources"), f"{path}.sources", file)


def validate_cross_stage(cross: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, cross, dict, path, file):
        return
    ensure_non_empty_str(errors, cross.get("name"), f"{path}.name", file)
    ensure_non_empty_str(errors, cross.get("description"), f"{path}.description", file)
    if expect_type(errors, cross.get("guidelines"), list, f"{path}.guidelines", file):
        for i, item in enumerate(cross["guidelines"]):
            ensure_non_empty_str(errors, item, f"{path}.guidelines[{i}]", file)


def validate_content(content: Any, file: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if not expect_type(errors, content, dict, "$", file):
        return errors

    if expect_type(errors, content.get("header"), dict, "$.header", file):
        for key in ("logo", "title", "subtitle"):
            ensure_non_empty_str(errors, content["header"].get(key), f"$.header.{key}", file)

    if expect_type(errors, content.get("stages"), list, "$.stages", file):
        if not content["stages"]:
            errors.append(ValidationError("$.stages must not be empty", file))
        for si, stage in enumerate(content["stages"]):
            validate_stage(stage, f"$.stages[{si}]", errors, file)

    if "cross_stage" in content:
        validate_cross_stage(content["cross_stage"], "$.cross_stage", errors, file)
    return errors


def validate_pages_config(config: Any) -> tuple[list[ValidationError], list[dict[str, Any]]]:
    errors: list[ValidationError] = []
    pages: list[dict[str, Any]] = []
    file = PAGES_FILE
    if not expect_type(errors, config, dict, "$", file):
        return errors, pages
    if not expect_type(errors, config.get("pages"), list, "$.pages", file):
        return errors, pages
    if not config["pages"]:
        errors.append(ValidationError("$.pages must not be empty", file))
        return errors, pages

    seen_keys: set[str] = set()
    seen_outputs: set[str] = set()
    for i, page in enumerate(config["pages"]):
        pp = f"$.pages[{i}]"
        if not expect_type(errors, page, dict, pp, file):
            continue
        for key in ("key", "label", "content_file", "output_file"):
            ensure_non_empty_str(errors, page.get(key), f"{pp}.{key}", file)
        page_key = page.get("key")
        output_file = page.get("output_file")
        content_file = page.get("content_file")
        if isinstance(page_key, str):
            if page_key in seen_keys:
                errors.append(ValidationError(f"{pp}.key must be unique; duplicate '{page_key}'", file))
            seen_keys.add(page_key)
        if isinstance(output_file, str):
            if not output_file.endswith('.html'):
                errors.append(ValidationError(f"{pp}.output_file must end with .html", file))
            if output_file == 'index.html':
                errors.append(ValidationError(f"{pp}.output_file must not be index.html because index.html is the tabbed shell", file))
            if output_file in seen_outputs:
                errors.append(ValidationError(f"{pp}.output_file must be unique; duplicate '{output_file}'", file))
            seen_outputs.add(output_file)
        if isinstance(content_file, str):
            if not content_file.endswith('.json'):
                errors.append(ValidationError(f"{pp}.content_file must end with .json", file))
            if not (ROOT / content_file).exists():
                errors.append(ValidationError(f"{pp}.content_file does not exist: {content_file}", file))
        pages.append(page)
    return errors, pages


def validate_control(control: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    file = CONTROL_FILE
    if not expect_type(errors, control, dict, "$", file):
        return errors
    ensure_non_empty_str(errors, control.get("output_file"), "$.output_file", file)
    if isinstance(control.get("output_file"), str):
        if not control["output_file"].endswith('.html'):
            errors.append(ValidationError("$.output_file must end with .html", file))
        if control["output_file"] == 'index.html':
            errors.append(ValidationError("$.output_file must not be index.html because index.html is the tabbed shell", file))
    if expect_type(errors, control.get("colors"), dict, "$.colors", file):
        if not control["colors"]:
            errors.append(ValidationError("$.colors must not be empty", file))
    if expect_type(errors, control.get("sections"), dict, "$.sections", file):
        for key, value in control["sections"].items():
            if not isinstance(value, bool):
                errors.append(ValidationError(f"$.sections.{key} expected bool, got {type(value).__name__}", file))
    return errors


def main() -> int:
    pages_config, pages_parse_errors = parse_with_location(PAGES_FILE, "workflow_pages.json")
    control, control_parse_errors = parse_with_location(CONTROL_FILE, "workflow_control.json")
    errors = pages_parse_errors + control_parse_errors
    pages: list[dict[str, Any]] = []

    if pages_config is not None:
        page_errors, pages = validate_pages_config(pages_config)
        errors.extend(page_errors)

    if control is not None:
        errors.extend(validate_control(control))

    for page in pages:
        content_file = ROOT / page["content_file"]
        content, parse_errors = parse_with_location(content_file, page["content_file"])
        errors.extend(parse_errors)
        if content is not None:
            errors.extend(validate_content(content, content_file))

    if errors:
        for error in errors:
            emit(error)
        print(f"Validation failed with {len(errors)} error(s).")
        return 1

    print("Validation passed: workflow_pages.json, workflow_control.json, and all page content JSON files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
