#!/usr/bin/env python3
"""Check that MS-DOS source files use CRLF endings and a Ctrl-Z EOF marker."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path


EOF_MARKER = b"\x1a"
SRC_PATTERNS = (
    "*.ASM",
    "*.C",
    "*.H",
    "*.PRJ",
    "MAKEFILE",
    "README.MD",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def iter_dos_text_files(src_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(src_dir.iterdir())
        if path.is_file()
        and any(fnmatch.fnmatchcase(path.name, pattern) for pattern in SRC_PATTERNS)
    ]


def line_ending_errors(body: bytes) -> list[str]:
    errors: list[str] = []

    for offset, byte in enumerate(body):
        if byte == 0x0A and (offset == 0 or body[offset - 1] != 0x0D):
            errors.append(f"contains LF without preceding CR at byte {offset}")
            break

    for offset, byte in enumerate(body):
        if byte == 0x0D and (offset + 1 >= len(body) or body[offset + 1] != 0x0A):
            errors.append(f"contains CR without following LF at byte {offset}")
            break

    return errors


def normalize(data: bytes) -> bytes:
    body = data[:-1] if data.endswith(EOF_MARKER) else data
    body = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return body.replace(b"\n", b"\r\n") + EOF_MARKER


def check_file(path: Path, *, fix: bool) -> list[str]:
    data = path.read_bytes()

    if fix:
        if EOF_MARKER in data[:-1]:
            return ["contains Ctrl-Z before the final byte; refusing to fix automatically"]

        fixed = normalize(data)
        if fixed != data:
            path.write_bytes(fixed)
        data = fixed

    errors: list[str] = []
    if not data.endswith(EOF_MARKER):
        errors.append("does not end with Ctrl-Z / 0x1A")

    body = data[:-1] if data.endswith(EOF_MARKER) else data
    if EOF_MARKER in body:
        errors.append("contains Ctrl-Z / 0x1A before the final byte")

    errors.extend(line_ending_errors(body))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint src files for MS-DOS CRLF endings and Ctrl-Z EOF marker."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="rewrite checked files with CRLF endings and a final Ctrl-Z marker",
    )
    args = parser.parse_args()

    src_dir = repo_root() / "src"
    failures: list[tuple[Path, list[str]]] = []

    for path in iter_dos_text_files(src_dir):
        errors = check_file(path, fix=args.fix)
        if errors:
            failures.append((path, errors))

    if failures:
        for path, errors in failures:
            relpath = path.relative_to(repo_root())
            for error in errors:
                print(f"{relpath}: {error}", file=sys.stderr)
        return 1

    action = "Fixed" if args.fix else "Checked"
    print(f"{action} {len(iter_dos_text_files(src_dir))} MS-DOS text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
