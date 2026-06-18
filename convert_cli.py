#!/usr/bin/env python3
"""
CLI: python convert_cli.py <file_or_dir> [output_dir]
"""
import sys
import os
from pathlib import Path
from converter import (
    convert_batch, convert, SUPPORTED_OFFICE, SUPPORTED_TEXT
)

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_cli.py <file_or_dir> [output_dir]")
        sys.exit(1)

    target = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else (
        os.path.dirname(target) if os.path.isfile(target) else os.getcwd()
    )

    allowed = SUPPORTED_OFFICE | SUPPORTED_TEXT

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        files = [
            str(p) for p in Path(target).rglob("*")
            if p.is_file() and p.suffix.lower() in allowed
        ]
    else:
        print(f"❌ Not found: {target}")
        sys.exit(1)

    if not files:
        print("No convertible files found.")
        sys.exit(0)

    def progress(i, total, path):
        print(f"[{i}/{total}] Converting: {Path(path).name}")

    print(f"Converting {len(files)} file(s) → {out_dir}")
    results = convert_batch(files, out_dir, on_progress=progress)

    ok = sum(1 for _, (status, _) in results.items() if status)
    print(f"\n✓ Success: {ok}/{len(results)}")
    for path, (status, msg) in results.items():
        marker = "✓" if status else "✗"
        print(f"  {marker} {Path(path).name}")
        if not status:
            print(f"      └─ {msg}")

if __name__ == "__main__":
    main()