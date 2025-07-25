"""
CLI Entry point.

The full arguments to specify a build are huge!

This cli simplifies it with a layer of abstraction.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.compiler import CompilerImpl
from fastled_wasm_compiler.dump_headers import HeaderDumper
from fastled_wasm_compiler.env_validation import (
    add_environment_arguments,
    ensure_environment_configured,
)
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
    fast_debug: bool
    quick: bool
    release: bool
    no_platformio: bool
    clear_ccache: bool
    update_fastled_src: Path | None
    strict: bool
    headers: Path | None
    add_src: bool
    no_pch_headers: bool

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
    parser.add_argument(
        "--fast-debug",
        action="store_true",
        help="Enable fast debug mode (faster iteration)",
    )
    parser.add_argument("--quick", action="store_true", help="Enable quick mode")
    parser.add_argument("--release", action="store_true", help="Enable release mode")
    parser.add_argument(
        "--all", action="store_true", help="Build all modes (debug, quick, release)"
    )

    parser.add_argument(
        "--no-platformio",
        action="store_true",
        help="Disable PlatformIO and use direct emcc calls instead (default: True since PlatformIO is deprecated)",
        default=True,  # Default to True since PlatformIO is deprecated
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat all compiler warnings as errors",
    )
    parser.add_argument(
        "--headers",
        type=Path,
        help="Output directory for header files dump (e.g., 'out/headers')",
    )
    parser.add_argument(
        "--add-src",
        action="store_true",
        help="Include source files (.c, .cpp, .ino) in addition to headers when using --headers",
    )
    parser.add_argument(
        "--no-pch-headers",
        action="store_true",
        help="Disable precompiled headers",
    )

    # Add environment variable arguments
    add_environment_arguments(parser)

    args = parser.parse_args()

    # Validate and configure environment variables
    ensure_environment_configured(args)

    # Set NO_PRECOMPILED_HEADERS environment variable if --no-pch-headers flag is used
    if args.no_pch_headers:
        os.environ["NO_PRECOMPILED_HEADERS"] = "1"

    # Set STRICT environment variable if --strict flag is used
    if args.strict:
        os.environ["STRICT"] = "1"

    # Handle --all flag by expanding to all three modes
    if args.all:
        args.debug = True
        args.fast_debug = True
        args.quick = True
        args.release = True

    # If no modes specified, default to all
    if not any([args.debug, args.fast_debug, args.quick, args.release]):
        args.debug = True
        args.fast_debug = True
        args.quick = True
        args.release = True

    out: CliArgs = CliArgs(
        compiler_root=args.compiler_root,
        assets_dirs=args.assets_dirs,
        mapped_dir=args.mapped_dir,
        keep_files=args.keep_files,
        profile=args.profile,
        debug=args.debug,
        fast_debug=args.fast_debug,
        quick=args.quick,
        release=args.release,
        no_platformio=args.no_platformio,
        clear_ccache=args.clear_ccache,
        update_fastled_src=args.update_fastled_src,
        strict=args.strict,
        headers=args.headers,
        add_src=args.add_src,
        no_pch_headers=args.no_pch_headers,
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
        no_platformio=cli_args.no_platformio,
        debug=cli_args.debug,
        fast_debug=cli_args.fast_debug,
        quick=cli_args.quick,
        release=cli_args.release,
        clear_ccache=cli_args.clear_ccache,
        strict=cli_args.strict,
    )
    # Derive build modes from boolean flags
    build_libs = []
    if cli_args.debug:
        build_libs.append("debug")
    if cli_args.fast_debug:
        build_libs.append("fast_debug")
    if cli_args.quick:
        build_libs.append("quick")
    if cli_args.release:
        build_libs.append("release")

    compiler = CompilerImpl(
        volume_mapped_src=cli_args.update_fastled_src,
        build_libs=build_libs,
    )
    err = compiler.compile(compile_args)
    if isinstance(err, Exception):
        print(f"Compilation error: {err}")
        return 1

    # Dump headers if requested
    if cli_args.headers:
        print("\n🔧 Dumping headers...")
        header_dumper = HeaderDumper(cli_args.headers, cli_args.add_src)
        header_dumper.dump_all_headers()
        print(f"✅ Headers dumped to: {cli_args.headers}")
        if not str(cli_args.headers).lower().endswith(".zip"):
            print(f"📄 Manifest: {cli_args.headers / 'manifest.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
