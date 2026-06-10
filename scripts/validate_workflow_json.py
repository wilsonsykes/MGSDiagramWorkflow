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


CONTENT_FILE = ROOT / "workflow_content.json"
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
    except Exception as exc:  # noqa: BLE001 - show precise parsing failure
        text = str(exc)
        line = None
        col = None
        m = re.search(r"line (\d+) column (\d+)", text)
        if m:
            line = int(m.group(1))
            col = int(m.group(2))
        errors.append(ValidationError(f"{label} parse error: {text}", path, line, col))
        return None, errors


def expect_type(
    errors: list[ValidationError],
    value: Any,
    expected: type,
    path: str,
    file: Path,
) -> bool:
    if isinstance(value, expected):
        return True
    errors.append(
        ValidationError(
            f"{path} expected {expected.__name__}, got {type(value).__name__}",
            file,
        )
    )
    return False


def ensure_str(errors: list[ValidationError], value: Any, path: str, file: Path) -> bool:
    if isinstance(value, str):
        return True
    errors.append(ValidationError(f"{path} must be a string", file))
    return False


def ensure_non_empty_str(
    errors: list[ValidationError], value: Any, path: str, file: Path
) -> bool:
    if isinstance(value, str) and value.strip():
        return True
    errors.append(ValidationError(f"{path} must be a non-empty string", file))
    return False

def is_section_block(entry: Any) -> bool:
    return isinstance(entry, dict) and ("section" in entry and "phases" in entry)


def looks_like_card(entry: Any) -> bool:
    return isinstance(entry, dict) and any(
        key in entry for key in ("id", "status", "name", "trigger")
    )


def validate_card(card: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, card, dict, path, file):
        return

    for key in ("id", "status", "name", "trigger"):
        ensure_non_empty_str(errors, card.get(key), f"{path}.{key}", file)

    if expect_type(errors, card.get("features"), list, f"{path}.features", file):
        if not card["features"]:
            errors.append(ValidationError(f"{path}.features must not be empty", file))
        for i, feat in enumerate(card["features"]):
            ensure_non_empty_str(errors, feat, f"{path}.features[{i}]", file)

    if expect_type(errors, card.get("approval"), list, f"{path}.approval", file):
        if not card["approval"]:
            errors.append(ValidationError(f"{path}.approval must not be empty", file))
        for i, appr in enumerate(card["approval"]):
            ap = f"{path}.approval[{i}]"
            if not expect_type(errors, appr, dict, ap, file):
                continue
            ensure_non_empty_str(errors, appr.get("role"), f"{ap}.role", file)
            ensure_non_empty_str(errors, appr.get("label"), f"{ap}.label", file)

    if expect_type(errors, card.get("data_outputs"), list, f"{path}.data_outputs", file):
        if not card["data_outputs"]:
            errors.append(ValidationError(f"{path}.data_outputs must not be empty", file))
        for i, item in enumerate(card["data_outputs"]):
            ensure_non_empty_str(errors, item, f"{path}.data_outputs[{i}]", file)

    if expect_type(errors, card.get("tags"), list, f"{path}.tags", file):
        if not card["tags"]:
            errors.append(ValidationError(f"{path}.tags must not be empty", file))
        for i, tag in enumerate(card["tags"]):
            tp = f"{path}.tags[{i}]"
            if not expect_type(errors, tag, dict, tp, file):
                continue
            missing = [k for k in ("text", "bg", "color") if k not in tag]
            if missing:
                errors.append(
                    ValidationError(f"{tp} missing keys: {', '.join(missing)}", file)
                )
                continue
            for key in ("text", "bg", "color"):
                ensure_non_empty_str(errors, tag.get(key), f"{tp}.{key}", file)

def validate_section_block(block: Any, path: str, errors: list[ValidationError], file: Path) -> None:
    if not expect_type(errors, block, dict, path, file):
        return

    ensure_non_empty_str(errors, block.get("section"), f"{path}.section", file)
    if "version" in block:
        ensure_non_empty_str(errors, block.get("version"), f"{path}.version", file)
    if "stage" in block and not isinstance(block.get("stage"), (int, str)):
        errors.append(ValidationError(f"{path}.stage must be int or string", file))
    if "note" in block:
        ensure_non_empty_str(errors, block.get("note"), f"{path}.note", file)

    if not expect_type(errors, block.get("phases"), list, f"{path}.phases", file):
        return
    if not block["phases"]:
        errors.append(ValidationError(f"{path}.phases must not be empty", file))
    for pi, phase in enumerate(block["phases"]):
        pp = f"{path}.phases[{pi}]"
        if not expect_type(errors, phase, dict, pp, file):
            continue
        ensure_non_empty_str(errors, phase.get("title"), f"{pp}.title", file)
        if "phase" in phase and not isinstance(phase.get("phase"), (int, str)):
            errors.append(ValidationError(f"{pp}.phase must be int or string", file))
        if "color" in phase:
            ensure_non_empty_str(errors, phase.get("color"), f"{pp}.color", file)

        if not expect_type(errors, phase.get("groups"), list, f"{pp}.groups", file):
            continue
        if not phase["groups"]:
            errors.append(ValidationError(f"{pp}.groups must not be empty", file))
        for gi, group in enumerate(phase["groups"]):
            gp = f"{pp}.groups[{gi}]"
            if not expect_type(errors, group, dict, gp, file):
                continue
            ensure_non_empty_str(errors, group.get("name"), f"{gp}.name", file)
            if not expect_type(errors, group.get("documents"), list, f"{gp}.documents", file):
                continue
            if not group["documents"]:
                errors.append(ValidationError(f"{gp}.documents must not be empty", file))
            for di, doc in enumerate(group["documents"]):
                dp = f"{gp}.documents[{di}]"
                if not expect_type(errors, doc, dict, dp, file):
                    continue
                ensure_non_empty_str(errors, doc.get("code"), f"{dp}.code", file)
                ensure_non_empty_str(errors, doc.get("name"), f"{dp}.name", file)


def validate_content(content: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    file = CONTENT_FILE
    if not expect_type(errors, content, dict, "$", file):
        return errors

    if expect_type(errors, content.get("header"), dict, "$.header", file):
        for key in ("logo", "title", "subtitle"):
            ensure_non_empty_str(errors, content["header"].get(key), f"$.header.{key}", file)

    if expect_type(errors, content.get("stages"), list, "$.stages", file):
        if not content["stages"]:
            errors.append(ValidationError("$.stages must not be empty", file))
        for si, stage in enumerate(content["stages"]):
            sp = f"$.stages[{si}]"
            if not expect_type(errors, stage, dict, sp, file):
                continue
            for key in ("romaji", "english"):
                ensure_non_empty_str(errors, stage.get(key), f"{sp}.{key}", file)
            if expect_type(errors, stage.get("cards"), list, f"{sp}.cards", file):
                if not stage["cards"]:
                    errors.append(ValidationError(f"{sp}.cards must not be empty", file))
                for ci, card in enumerate(stage["cards"]):
                    cp = f"{sp}.cards[{ci}]"
                    if is_section_block(card):
                        validate_section_block(card, cp, errors, file)
                    elif looks_like_card(card):
                        validate_card(card, cp, errors, file)
                    else:
                        errors.append(
                            ValidationError(
                                f"{cp} must be either a standard card block or a checklist section block",
                                file,
                            )
                        )

    if expect_type(errors, content.get("manual_stages"), list, "$.manual_stages", file):
        if len(content["manual_stages"]) != len(content.get("stages", [])):
            errors.append(
                ValidationError(
                    "$.manual_stages count must match $.stages count",
                    file,
                )
            )
        for mi, stage in enumerate(content["manual_stages"]):
            mp = f"$.manual_stages[{mi}]"
            if not expect_type(errors, stage, dict, mp, file):
                continue
            if expect_type(errors, stage.get("pain_points"), list, f"{mp}.pain_points", file):
                if not stage["pain_points"]:
                    errors.append(ValidationError(f"{mp}.pain_points must not be empty", file))
                for pi, point in enumerate(stage["pain_points"]):
                    ensure_non_empty_str(errors, point, f"{mp}.pain_points[{pi}]", file)

    return errors


def validate_control(control: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    file = CONTROL_FILE
    if not expect_type(errors, control, dict, "$", file):
        return errors

    ensure_non_empty_str(errors, control.get("output_file"), "$.output_file", file)
    if isinstance(control.get("output_file"), str) and not control["output_file"].endswith(".html"):
        errors.append(ValidationError("$.output_file must end with .html", file))
    if expect_type(errors, control.get("colors"), dict, "$.colors", file):
        if not control["colors"]:
            errors.append(ValidationError("$.colors must not be empty", file))
    if expect_type(errors, control.get("sections"), dict, "$.sections", file):
        for key, value in control["sections"].items():
            if not isinstance(value, bool):
                errors.append(
                    ValidationError(
                        f"$.sections.{key} expected bool, got {type(value).__name__}",
                        file,
                    )
                )
    return errors


def main() -> int:
    content, parse_errors = parse_with_location(CONTENT_FILE, "workflow_content.json")
    control, control_parse_errors = parse_with_location(CONTROL_FILE, "workflow_control.json")
    errors = parse_errors + control_parse_errors

    if content is not None:
        errors.extend(validate_content(content))
    if control is not None:
        errors.extend(validate_control(control))

    if errors:
        for error in errors:
            emit(error)
        print(f"Validation failed with {len(errors)} error(s).")
        return 1

    print("Validation passed: workflow_content.json and workflow_control.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
