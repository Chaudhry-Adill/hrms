#!/usr/bin/env python3
"""PostToolUse hook for Claude Code.

Runs ruff on edited Python files and prettier on edited JS/Vue/CSS files.
Reads file paths from the CLAUDE_FILE_PATHS environment variable.
"""

import json
import os
import subprocess
import sys


EXTENSIONS_PRETTIER = (
    ".js",
    ".vue",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".json",
    ".md",
    ".yaml",
    ".yml",
)


def get_file_paths() -> list[str]:
    """Retrieve edited file paths from env or stdin."""
    paths = os.environ.get("CLAUDE_FILE_PATHS", "")
    if paths:
        return [p.strip() for p in paths.replace("\n", " ").split() if p.strip()]

    # Fallback: parse stdin JSON for tool_input.file_path
    try:
        data = json.load(sys.stdin)
        file_path = data.get("tool_input", {}).get("file_path", "")
        if file_path:
            return [file_path]
    except Exception:
        pass

    return []


def run_ruff(files: list[str]) -> None:
    py_files = [f for f in files if f.endswith(".py")]
    if not py_files:
        return

    subprocess.run(
        ["ruff", "check", "--fix"] + py_files,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["ruff", "format"] + py_files,
        capture_output=True,
        check=False,
    )


def run_prettier(files: list[str]) -> None:
    all_files = [f for f in files if f.endswith(EXTENSIONS_PRETTIER)]
    if not all_files:
        return

    root_files = [f for f in all_files if not f.startswith(("frontend/", "roster/"))]
    frontend_files = [f for f in all_files if f.startswith("frontend/")]
    roster_files = [f for f in all_files if f.startswith("roster/")]

    if root_files:
        subprocess.run(
            ["npx", "prettier", "--write"] + root_files,
            capture_output=True,
            check=False,
        )

    if frontend_files:
        rel = [f.replace("frontend/", "", 1) for f in frontend_files]
        subprocess.run(
            ["npx", "prettier", "--write"] + rel,
            cwd="frontend",
            capture_output=True,
            check=False,
        )

    if roster_files:
        rel = [f.replace("roster/", "", 1) for f in roster_files]
        subprocess.run(
            ["npx", "prettier", "--write"] + rel,
            cwd="roster",
            capture_output=True,
            check=False,
        )


def main() -> int:
    files = get_file_paths()
    if not files:
        return 0

    run_ruff(files)
    run_prettier(files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
