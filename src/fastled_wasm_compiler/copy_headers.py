import argparse
import shutil
import sys
from dataclasses import dataclass
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
