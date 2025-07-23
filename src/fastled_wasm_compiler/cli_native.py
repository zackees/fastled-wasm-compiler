"""
CLI Entry point for Native EMSDK Compilation.

This CLI provides native compilation functionality using locally installed EMSDK
instead of Docker containers. It downloads and manages EMSDK automatically.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.compile_sketch_native import compile_sketch_native
from fastled_wasm_compiler.dump_headers import HeaderDumper
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
from fastled_wasm_compiler.env_validation import (
    add_environment_arguments,
    ensure_environment_configured,
)


@dataclass
class NativeCliArgs:
    sketch_dir: Path
    build_mode: str
    output_dir: Path | None
    emsdk_dir: Path | None
    install_emsdk: bool
    keep_files: bool
    profile: bool
    strict: bool
    headers: Path | None
    add_src: bool

    @staticmethod
    def parse_args() -> "NativeCliArgs":
        return _parse_args()


def _parse_args() -> NativeCliArgs:
    parser = argparse.ArgumentParser(
        description="Compile FastLED sketches using native EMSDK (no Docker required)"
    )

    parser.add_argument(
        "sketch_dir",
        type=Path,
        help="Directory containing sketch source files (.ino, .cpp)",
    )

    parser.add_argument(
        "--mode",
        choices=["debug", "fast_debug", "quick", "release"],
        default="debug",
        help="Build mode (default: debug)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for compiled files (default: sketch_dir/fastled_js)",
    )

    parser.add_argument(
        "--emsdk-dir", type=Path, help="Custom EMSDK installation directory"
    )

    parser.add_argument(
        "--install-emsdk", action="store_true", help="Install EMSDK if not present"
    )

    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep intermediate build files after compilation",
    )

    parser.add_argument(
        "--profile", action="store_true", help="Enable profiling of the build system"
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

    # Add environment variable arguments
    add_environment_arguments(parser)

    args = parser.parse_args()

    # Validate and configure environment variables (only if not just installing EMSDK)
    if not args.install_emsdk:
        ensure_environment_configured(args)

    # Set STRICT environment variable if --strict flag is used
    if args.strict:
        os.environ["STRICT"] = "1"

    out: NativeCliArgs = NativeCliArgs(
        sketch_dir=args.sketch_dir,
        build_mode=args.mode,
        output_dir=args.output_dir,
        emsdk_dir=args.emsdk_dir,
        install_emsdk=args.install_emsdk,
        keep_files=args.keep_files,
        profile=args.profile,
        strict=args.strict,
        headers=args.headers,
        add_src=args.add_src,
    )
    return out


def main() -> int:
    """Main entry point for the native FastLED WASM compiler."""
    cli_args = None
    try:
        cli_args = NativeCliArgs.parse_args()

        # Install EMSDK if requested and exit
        if cli_args.install_emsdk:
            print("Installing EMSDK...")
            manager = get_emsdk_manager(cli_args.emsdk_dir)
            manager.install()
            print("✅ EMSDK installation complete")
            return 0

        # Validate sketch directory (only if not just installing EMSDK)
        if not cli_args.sketch_dir.exists():
            print(f"❌ Sketch directory not found: {cli_args.sketch_dir}")
            return 1

        # Compile sketch
        print(f"🔨 Compiling sketch: {cli_args.sketch_dir}")
        print(f"📋 Build mode: {cli_args.build_mode}")
        if cli_args.output_dir:
            print(f"📁 Output directory: {cli_args.output_dir}")
        if cli_args.emsdk_dir:
            print(f"🛠️  EMSDK directory: {cli_args.emsdk_dir}")

        js_file = compile_sketch_native(
            sketch_dir=cli_args.sketch_dir,
            build_mode=cli_args.build_mode,
            output_dir=cli_args.output_dir,
            emsdk_install_dir=cli_args.emsdk_dir,
        )

        print("\n✅ Compilation successful!")
        print(f"📄 JavaScript: {js_file}")
        print(f"🔧 WASM: {js_file.with_suffix('.wasm')}")

        # Dump headers if requested
        if cli_args.headers:
            print(f"\n🔧 Dumping headers to: {cli_args.headers}")
            header_dumper = HeaderDumper(cli_args.headers, cli_args.add_src)
            header_dumper.dump_all_headers()
            print(f"✅ Headers dumped to: {cli_args.headers}")
            print(f"📄 Manifest: {cli_args.headers / 'manifest.json'}")

        # Clean up intermediate files if not keeping them
        if not cli_args.keep_files:
            build_dir = js_file.parent / "build"
            if build_dir.exists():
                import shutil

                shutil.rmtree(build_dir, ignore_errors=True)
                print(f"🧹 Cleaned up build directory: {build_dir}")

        return 0

    except Exception as e:
        print(f"\n❌ Compilation failed: {e}")
        # Show traceback if profiling is enabled or if parsing failed
        if cli_args is not None and cli_args.profile:
            import traceback

            traceback.print_exc()
        elif cli_args is None:
            # Argument parsing failed, show traceback anyway
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
