import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from queue import Queue


class BuildMode(Enum):
    DEBUG = auto()
    QUICK = auto()
    RELEASE = auto()

    @classmethod
    def from_string(cls, mode_str: str) -> "BuildMode":
        mode_str = mode_str.upper()
        if mode_str == "DEBUG":
            return cls.DEBUG
        elif mode_str == "QUICK":
            return cls.QUICK
        elif mode_str == "RELEASE":
            return cls.RELEASE
        else:
            raise ValueError(f"Unknown build mode: {mode_str}")


@dataclass
class Args:
    src: Path
    out: Path
    build_mode: BuildMode = BuildMode.DEBUG

    @staticmethod
    def parse_args(cmd_list: list[str] | None = None) -> "Args":
        args: argparse.Namespace = _parse_args(cmd_list)

        # Determine build mode
        if args.release:
            build_mode = BuildMode.RELEASE
        elif args.quick:
            build_mode = BuildMode.QUICK
        elif args.debug:
            build_mode = BuildMode.DEBUG
        else:
            # Default to debug if no mode specified
            raise ValueError(
                "No build mode specified. Use --debug, --quick, or --release."
            )

        return Args(src=args.src, out=args.out, build_mode=build_mode)


# _PRINT_LOCK = Lock()
_PRINT_QUEUE = Queue()


def _print_worker():
    while True:
        msg = _PRINT_QUEUE.get()
        if msg is None:
            break
        print(msg)
        _PRINT_QUEUE.task_done()


_THREADED_PRINT = threading.Thread(
    target=_print_worker, daemon=True, name="PrintWorker"
)
_THREADED_PRINT.start()


def _locked_print(s: str) -> None:
    """Thread-safe print function."""
    _PRINT_QUEUE.put(s)


def build_static_lib(
    src_dir: Path,
    build_dir: Path,
    build_mode: BuildMode = BuildMode.QUICK,
    max_workers: int | None = None,
) -> int:
    if not src_dir.is_dir():
        _locked_print(f"Error: '{src_dir}' is not a directory.")
        return 1

    cwd = "/git/build"
    cmd = f"build_lib.sh --{build_mode.name}"
    print(f"Building {build_mode.name} in {cwd}")
    start = time.time()
    rtn = subprocess.call(cmd, shell=True, cwd=cwd)
    end = time.time()
    print(f"Build {build_mode.name} took {end - start:.2f} seconds")
    return rtn


def _parse_args(cmd_list: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static .a library from source files."
    )
    parser.add_argument(
        "--src",
        type=Path,
        required=True,
        help="Source directory containing .cpp/.ino files",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for .o and .a files"
    )

    # Build mode arguments (mutually exclusive)
    build_mode_group = parser.add_mutually_exclusive_group()
    build_mode_group.add_argument(
        "--debug", action="store_true", help="Build with debug flags (default)"
    )
    build_mode_group.add_argument(
        "--quick", action="store_true", help="Build with light optimization (O1)"
    )
    build_mode_group.add_argument(
        "--release", action="store_true", help="Build with aggressive optimization (Oz)"
    )

    # Parse arguments
    args = parser.parse_args(cmd_list)
    return args


def main() -> int:
    args = Args.parse_args()

    _locked_print(f"Building with mode: {args.build_mode.name}")
    rtn = build_static_lib(args.src, args.out, args.build_mode)
    _PRINT_QUEUE.put(None)  # Signal the print worker to exit
    # _PRINT_QUEUE.join()  # Wait for all queued prints to finish
    _THREADED_PRINT.join()  # Wait for the print worker to finish
    return rtn


if __name__ == "__main__":
    sys.exit(main())
