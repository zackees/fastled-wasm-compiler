import argparse
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.compile_all_libs import (
    ArchiveType,
    BuildResult,
    compile_all_libs,
)
from fastled_wasm_compiler.paths import BUILD_ROOT
from fastled_wasm_compiler.types import BuildMode


def _locked_print(msg: str) -> None:
    print(msg)


@dataclass
class Args:
    src: Path
    build_dir: Path
    build_mode: BuildMode

    @staticmethod
    def parse_args() -> "Args":
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(description="Compile FastLED library")
        parser.add_argument(
            "--src",
            type=Path,
            required=True,
            help="Path to FastLED source directory",
        )
        parser.add_argument(
            "--build-dir",
            type=Path,
            required=True,
            help="Build directory for output",
        )
        build_group = parser.add_mutually_exclusive_group(required=True)
        build_group.add_argument(
            "--debug", action="store_true", help="Build in debug mode"
        )
        build_group.add_argument(
            "--quick", action="store_true", help="Build in quick mode"
        )
        build_group.add_argument(
            "--release", action="store_true", help="Build in release mode"
        )

        args = parser.parse_args()

        # Determine build mode
        if args.debug:
            build_mode = BuildMode.DEBUG
        elif args.quick:
            build_mode = BuildMode.QUICK
        elif args.release:
            build_mode = BuildMode.RELEASE
        else:
            raise ValueError("Must specify one of --debug, --quick, or --release")

        return Args(
            src=args.src,
            build_dir=args.build_dir,
            build_mode=build_mode,
        )


def build_static_lib(
    src_dir: Path,
    build_dir: Path,
    build_mode: BuildMode = BuildMode.QUICK,
    max_workers: int | None = None,
) -> int:
    if not src_dir.is_dir():
        _locked_print(f"Error: '{src_dir}' is not a directory.")
        return 1

    cwd = os.environ.get("ENV_BUILD_CWD", "/git/build")
    cmd = f"build_lib.sh --{build_mode.name}"

    # Set environment variables for command line usage
    env = os.environ.copy()
    # Ensure thin archives are built (NO_THIN_LTO not set)
    env.pop("NO_THIN_LTO", None)

    print(f"Building {build_mode.name} thin archive for command line usage in {cwd}")
    start = time.time()
    rtn = subprocess.call(cmd, shell=True, cwd=cwd, env=env)
    end = time.time()
    print(f"Build {build_mode.name} took {end - start:.2f} seconds")
    return rtn


def main() -> int:
    """Main entry point for compile_lib."""
    args = Args.parse_args()

    print("Compiling FastLED library")
    print(f"Source: {args.src}")
    print(f"Build directory: {args.build_dir}")
    print(f"Build mode: {args.build_mode.name}")

    # Use the centralized compile_all_libs function with THIN archives for command line usage
    result: BuildResult = compile_all_libs(
        src=str(args.src),
        out=str(BUILD_ROOT),  # Use standard build root
        build_modes=[args.build_mode.name.lower()],
        archive_type=ArchiveType.THIN,  # Command line usage only builds thin archives
    )

    if result.return_code == 0:
        print("✅ Library compilation completed successfully")

        # Verify the thin archive was created
        mode_str = args.build_mode.name.lower()
        thin_lib = BUILD_ROOT / mode_str / "libfastled-thin.a"
        if thin_lib.exists():
            size = thin_lib.stat().st_size
            print(f"✅ Thin archive created: {thin_lib} ({size} bytes)")
        else:
            print(f"❌ Expected thin archive not found: {thin_lib}")
            return 1
    else:
        print(f"❌ Library compilation failed with exit code {result.return_code}")

    return result.return_code


if __name__ == "__main__":
    import sys

    sys.exit(main())
