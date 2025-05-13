import shutil
import sys
from pathlib import Path


def copy_headers(start_dir: Path, out_dir: Path) -> None:
    if not start_dir.is_dir():
        print(f"Error: '{start_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    for header in start_dir.rglob("*"):
        if header.suffix.lower() in {".h", ".hpp"}:
            rel_path = header.relative_to(start_dir)
            dest = out_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(header, dest)
            print(f"Copied: {header} → {dest}")
