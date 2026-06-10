#!/usr/bin/env python3
"""
Fail when index.html is edited directly by a non-bot change.
"""

from __future__ import annotations

import os
import subprocess
import sys


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def changed_files_for_push() -> list[str]:
    before = os.environ.get("GITHUB_EVENT_BEFORE", "")
    head = os.environ.get("GITHUB_SHA", "")
    if not head:
        output = run_git(["status", "--short"])
        files: list[str] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            files.append(line[3:].strip())
        return files
    if before and before != "0000000000000000000000000000000000000000":
        output = run_git(["diff", "--name-only", before, head])
        return [line for line in output.splitlines() if line]
    output = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", head])
    return [line for line in output.splitlines() if line]


def changed_files_for_pr() -> list[str]:
    base = os.environ.get("GITHUB_BASE_SHA", "")
    head = os.environ.get("GITHUB_HEAD_SHA", "")
    output = run_git(["diff", "--name-only", base, head])
    return [line for line in output.splitlines() if line]


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "push")
    if event_name == "pull_request":
        files = changed_files_for_pr()
    else:
        files = changed_files_for_push()

    if "index.html" in files:
        print(
            "::error file=index.html,title=Index Guard::Direct edits to index.html are blocked. "
            "Edit workflow_content.json or workflow_control.json and let GitHub Actions regenerate index.html."
        )
        print("Changed files:", ", ".join(files))
        return 1

    print("Index guard passed: no direct index.html edits detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
