import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

_INCLUSION_DIRS = ["platforms/wasm", "platforms/stub"]


def copy_headers(start_dir: Path, out_dir: Path) -> None:
    if not start_dir.is_dir():
        print(f"Error: '{start_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(start_dir, topdown=True):
        root_path = Path(root)
        rel_root = root_path.relative_to(start_dir)
        rel_root_str = str(rel_root)

        # Check if we're in a platforms subdirectory
        parts = rel_root.parts
        in_platforms = len(parts) >= 1 and parts[0] == "platforms"

        # Check if we're in an inclusion directory
        in_inclusion = any(incl in rel_root_str for incl in _INCLUSION_DIRS)

        # Skip traversing this directory if it's in platforms but not in inclusion
        if in_platforms and not in_inclusion and rel_root_str != "platforms":
            print(f"Skipping directory: {rel_root}")
            dirs.clear()  # This prevents os.walk from recursing into subdirectories
            continue

        # Process header files in this directory
        for file in files:
            if file.lower().endswith((".h", ".hpp")):
                src_file = root_path / file
                rel_path = src_file.relative_to(start_dir)
                dest_file = out_dir / rel_path

                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                print(f"Copied: {src_file} → {dest_file}")


@dataclass
class Args:
    start_dir: Path
    out_dir: Path

    @staticmethod
    def parse_args(args: list[str] | None = None) -> "Args":
        args2: argparse.Namespace = _parse_args(args)
        return Args(
            start_dir=args2.start_dir,
            out_dir=args2.out_dir,
        )

    def __post_init__(self):
        assert isinstance(self.start_dir, Path), f"{self.start_dir} is not a Path"
        assert isinstance(self.out_dir, Path), f"{self.out_dir} is not a Path"
        assert self.start_dir.exists(), f"{self.start_dir} does not exist"
        assert self.out_dir.exists(), f"{self.out_dir} does not exist"
        assert self.start_dir.is_dir(), f"{self.start_dir} is not a directory"
        assert self.out_dir.is_dir(), f"{self.out_dir} is not a directory"


def _parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy all .h and .hpp files from a directory to another directory."
    )
    parser.add_argument(
        "start_dir", type=Path, help="The directory to copy headers from."
    )
    parser.add_argument("out_dir", type=Path, help="The directory to copy headers to.")
    return parser.parse_args(args)


def main() -> int:
    args = Args.parse_args()
    try:
        copy_headers(args.start_dir, args.out_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
