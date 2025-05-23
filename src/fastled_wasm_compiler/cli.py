"""
CLI Entry point.

The full arguments to specify a build are huge!

This cli simplifies it with a layer of abstraction.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.compiler import Compiler
from fastled_wasm_compiler.paths import FASTLED_SRC, SKETCH_ROOT
from fastled_wasm_compiler.run_compile import Args

_DEFAULT_ASSETS_DIR = FASTLED_SRC / "platforms" / "wasm" / "compiler"


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
    update_fastled_src: Path | None

    @staticmethod
    def parse_args() -> "CliArgs":
        return _parse_args()


def _parse_args() -> CliArgs:
    parser = argparse.ArgumentParser(description="Compile FastLED for WASM")

    parser.add_argument("--compiler-root", type=Path, default=SKETCH_ROOT)
    parser.add_argument(
        "--assets-dirs",
        type=Path,
        default=_DEFAULT_ASSETS_DIR,
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
    parser.add_argument(
        "--update-fastled-src",
        type=Path,
        help="Path to the FastLED source directory to update",
        default=None,
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
        update_fastled_src=args.update_fastled_src,
    )
    return out


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    cli_args = CliArgs.parse_args()
    compile_args: Args = Args(
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
    compiler = Compiler(
        volume_mapped_src=cli_args.update_fastled_src,
    )
    err = compiler.compile(compile_args)
    if isinstance(err, Exception):
        print(f"Compilation error: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
