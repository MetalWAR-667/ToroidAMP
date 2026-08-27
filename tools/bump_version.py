"""
ToroidAMP - Version Bump Utility

Bumps the canonical version in pyproject.toml's `[project].version`.

Metadata-only. This tool never touches Git — no commit, tag, push, or
staging. That is Metal's job. Version changes happen at cut CLOSURE, not
merely because implementation or tests happened.

Usage:
    python tools\\bump_version.py patch
    python tools\\bump_version.py minor
    python tools\\bump_version.py major
"""

import argparse
import re
import sys
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"

# Deliberately narrow: only the `version = "X.Y.Z"` line under [project].
# The actual bump arithmetic below is semantic (integer parsing + increment),
# not string manipulation — this regex only locates and rewrites that one line.
VERSION_LINE_RE = re.compile(r'^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")', re.MULTILINE)


def read_version(text: str) -> tuple[int, int, int]:
    match = VERSION_LINE_RE.search(text)
    if not match:
        raise ValueError(f'Could not find a `version = "X.Y.Z"` line in {PYPROJECT_PATH}')
    return int(match.group(2)), int(match.group(3)), int(match.group(4))


def bump(current: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    if part == "patch":
        return major, minor, patch + 1
    raise ValueError(f"Unknown version part: {part}")


def write_version(text: str, new_version: tuple[int, int, int]) -> str:
    major, minor, patch = new_version
    return VERSION_LINE_RE.sub(rf"\g<1>{major}.{minor}.{patch}\g<5>", text, count=1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bump ToroidAMP's canonical version in pyproject.toml. "
            "Metadata-only — never commits, tags, stages, or pushes."
        )
    )
    parser.add_argument("part", choices=["major", "minor", "patch"])
    args = parser.parse_args(argv)

    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    current = read_version(text)
    new_version = bump(current, args.part)
    new_text = write_version(text, new_version)
    PYPROJECT_PATH.write_text(new_text, encoding="utf-8")

    old_str = ".".join(map(str, current))
    new_str = ".".join(map(str, new_version))
    print(f"ToroidAMP version: {old_str} -> {new_str} ({args.part})")
    print(f"Updated: {PYPROJECT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
