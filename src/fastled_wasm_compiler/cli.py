"""
CLI Entry point.

The full arguments to specify a build are huge!

This cli simplifies it with a layer of abstraction.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.run import Args, run


@dataclass
class CliArgs:
    compiler_root: Path
    assets_dirs: Path
    mapped_dir: Path
    keep_files: bool
    profile: bool
    debug: bool
    quick: bool
    release: bool
    no_platformio: bool
    clear_ccache: bool

    @staticmethod
    def parse_args() -> "CliArgs":
        return _parse_args()


def _parse_args() -> CliArgs:
    parser = argparse.ArgumentParser(description="Compile FastLED for WASM")

    parser.add_argument("--compiler-root", type=Path, required=True)
    parser.add_argument(
        "--assets-dirs",
        type=Path,
        required=True,
        help="directory where index.html, index.js, etc are kept",
    )
    # Important: This directory structure weird.
    # It needs two levels. See examples in the code of how this is set.
    parser.add_argument(
        "--mapped-dir",
        type=Path,
        default="/mapped",
        help="Directory containing source files (default: /mapped)",
    )
    parser.add_argument(
        "--keep-files", action="store_true", help="Keep source files after compilation"
    )
    parser.add_argument(
        "--profile", action="store_true", help="Enable profiling of the build system"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--quick", action="store_true", help="Enable quick mode")
    parser.add_argument("--release", action="store_true", help="Enable release mode")

    parser.add_argument(
        "--no-platformio",
        action="store_true",
        help="Disable PlatformIO (not implemented yet)",
    )
    parser.add_argument(
        "--clear-ccache",
        action="store_true",
        help="Clear the ccache before compilation",
    )

    args = parser.parse_args()
    out: CliArgs = CliArgs(
        compiler_root=args.compiler_root,
        assets_dirs=args.assets_dirs,
        mapped_dir=args.mapped_dir,
        keep_files=args.keep_files,
        profile=args.profile,
        debug=args.debug,
        quick=args.quick,
        release=args.release,
        no_platformio=args.no_platformio,
        clear_ccache=args.clear_ccache,
    )
    return out


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    cli_args = CliArgs.parse_args()
    full_args: Args = Args(
        compiler_root=cli_args.compiler_root,
        assets_dirs=cli_args.assets_dirs,
        mapped_dir=cli_args.mapped_dir,
        keep_files=cli_args.keep_files,
        only_copy=False,
        only_insert_header=False,
        only_compile=False,
        profile=cli_args.profile,
        disable_auto_clean=False,
        no_platformio=False,
        debug=cli_args.debug,
        quick=cli_args.quick,
        release=cli_args.release,
        clear_ccache=cli_args.clear_ccache,
    )
    rtn = run(full_args)
    return rtn


if __name__ == "__main__":
    sys.exit(main())
