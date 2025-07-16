"""
CLI Entry point.

The full arguments to specify a build are huge!

This cli simplifies it with a layer of abstraction.
"""

import argparse
import os
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from fastled_wasm_compiler.env_validation import (
    add_environment_arguments,
    ensure_environment_configured,
)
from fastled_wasm_compiler.paths import SKETCH_ROOT
from fastled_wasm_compiler.run_compile import Args, run_compile
from fastled_wasm_compiler.types import BuildMode


@dataclass
class CliArgs:
    sketch: Path
    assets: Path
    build: BuildMode

    @staticmethod
    def parse_args() -> "CliArgs":
        return _parse_args()


def _build_fastled_libraries(build_mode: str) -> int:
    """Build both thin and regular FastLED libraries for the given build mode.

    Args:
        build_mode: One of "debug", "quick", "release"

    Returns:
        0 if successful, non-zero if any build failed
    """
    print(f"\n🏗️  Building FastLED libraries for {build_mode} mode...")

    # Build thin archives (NO_THIN_LTO=0)
    print(f"📦 Building thin archives for {build_mode}...")
    env_thin = os.environ.copy()
    env_thin["NO_THIN_LTO"] = "0"

    cmd_thin = ["/build/build_lib.sh", f"--{build_mode}"]
    result_thin = subprocess.run(cmd_thin, env=env_thin, cwd="/git/fastled-wasm")
    if result_thin.returncode != 0:
        print(f"❌ Failed to build thin archives for {build_mode}")
        return result_thin.returncode
    print(f"✅ Thin archives built successfully for {build_mode}")

    # Build regular archives (NO_THIN_LTO=1)
    print(f"📦 Building regular archives for {build_mode}...")
    env_regular = os.environ.copy()
    env_regular["NO_THIN_LTO"] = "1"

    cmd_regular = ["/build/build_lib.sh", f"--{build_mode}"]
    result_regular = subprocess.run(
        cmd_regular, env=env_regular, cwd="/git/fastled-wasm"
    )
    if result_regular.returncode != 0:
        print(f"❌ Failed to build regular archives for {build_mode}")
        return result_regular.returncode
    print(f"✅ Regular archives built successfully for {build_mode}")

    print(f"🎉 Both archive types built successfully for {build_mode}")
    return 0


def _parse_args() -> CliArgs:
    parser = argparse.ArgumentParser(description="Compile FastLED for WASM")
    parser.add_argument(
        "--sketch",
        type=Path,
        required=True,
        help="Path to sketch",
    )
    # Important: This directory structure weird.
    # It needs two levels. See examples in the code of how this is set.
    parser.add_argument(
        "--assets-dir",
        type=Path,
        required=True,
        help="Directory containing source files (default: /mapped)",
    )

    build_parser = parser.add_mutually_exclusive_group(required=True)

    build_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    build_parser.add_argument("--quick", action="store_true", help="Enable quick mode")
    build_parser.add_argument(
        "--release", action="store_true", help="Enable release mode"
    )

    # Add environment variable arguments
    add_environment_arguments(parser)

    args = parser.parse_args()

    # Validate and configure environment variables
    ensure_environment_configured(args)
    build_mode: BuildMode

    if args.debug:
        build_mode = BuildMode.DEBUG
    elif args.quick:
        build_mode = BuildMode.QUICK
    elif args.release:
        build_mode = BuildMode.RELEASE
    else:
        raise ValueError("Invalid build mode")

    out: CliArgs = CliArgs(
        sketch=args.sketch,
        assets=args.assets_dir,
        build=build_mode,
    )
    return out


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    cli_args = CliArgs.parse_args()
    print(f"Sketch: {cli_args.sketch}")
    assert cli_args.sketch.is_dir(), f"{cli_args.sketch} is not a directory!"

    print(f"Inspecting sketch directory: {cli_args.sketch}")
    # os.system(f"ls -al {cli_args.sketch}")
    # do an os walk instead
    for root, _, files in os.walk(cli_args.sketch):
        for name in files:
            full_path = os.path.join(root, name)
            print(f"File: {full_path}")

    build = cli_args.build
    build_mode_str = build.name.lower()

    # First, build both thin and regular FastLED libraries
    print(f"\n🚀 Prewarm: Building FastLED libraries for {build_mode_str} mode...")
    lib_result = _build_fastled_libraries(build_mode_str)
    if lib_result != 0:
        print(f"❌ Failed to build FastLED libraries for {build_mode_str}")
        return lib_result

    # Then compile the sketch (this will use thin archives since NO_THIN_LTO defaults to 0)
    print(f"\n🔨 Prewarm: Compiling sketch for {build_mode_str} mode...")
    compiler_root = SKETCH_ROOT
    # assert compiler_root.exists(), f"{compiler_root} does not exist!"
    # assert compiler_root.is_dir(), f"{compiler_root} is a file!"
    mapped_dir = cli_args.sketch.parent
    print(f"mapped_dir: {mapped_dir}")
    try:
        compiler_root.mkdir(parents=True, exist_ok=True)
        item: Path
        # Clean out the old path.
        for item in compiler_root.iterdir():
            if item.is_file():
                print(f"Removing {item}")
                os.unlink(item)
            if item.is_dir():
                print(f"Removing {item}")
                shutil.rmtree(item)

        # shutil.copytree(cli_args.sketch, compiler_root / "src")
        # copy each of the files in cli_args.sketch to the compiler_root/src
        dst = compiler_root / "src"
        if not dst.exists():
            dst.mkdir(parents=True, exist_ok=True)
        for item in cli_args.sketch.iterdir():
            if item.is_file():
                print(f"copying {item} to {dst / item.name}")
                shutil.copy(item, dst / item.name)
            if item.is_dir():
                print(f"copying {item} to {dst / item.name}")
                shutil.copytree(item, dst / item.name)

        # Ensure we use thin archives for the sketch compilation (default behavior)
        os.environ.pop("NO_THIN_LTO", None)

        full_args: Args = Args(
            compiler_root=compiler_root,  # TODO: Remove this
            assets_dirs=cli_args.assets,
            mapped_dir=mapped_dir,  # For reasons, it needs to be the parent directory.
            keep_files=False,
            only_copy=False,
            only_insert_header=False,
            only_compile=False,
            profile=False,
            disable_auto_clean=False,
            no_platformio=False,
            debug=build == BuildMode.DEBUG,
            quick=build == BuildMode.QUICK,
            release=build == BuildMode.RELEASE,
            clear_ccache=False,
            strict=False,
        )
        rtn = run_compile(full_args)
        if rtn != 0:
            print("Error: Compiler failed without an exception")
            return rtn

        print(f"🎉 Prewarm completed successfully for {build_mode_str} mode!")
        print("📚 Available archives:")
        build_root = os.environ.get("ENV_BUILD_ROOT", "/build")
        thin_lib = Path(f"{build_root}/{build_mode_str}/libfastled-thin.a")
        regular_lib = Path(f"{build_root}/{build_mode_str}/libfastled.a")

        if thin_lib.exists():
            size = thin_lib.stat().st_size
            print(f"  ✅ Thin archive: {thin_lib} ({size} bytes)")
        else:
            print(f"  ❌ Missing thin archive: {thin_lib}")

        if regular_lib.exists():
            size = regular_lib.stat().st_size
            print(f"  ✅ Regular archive: {regular_lib} ({size} bytes)")
        else:
            print(f"  ❌ Missing regular archive: {regular_lib}")

        return rtn
    except FileNotFoundError as e:
        import traceback

        stacktrace = traceback.format_exc()
        print(stacktrace)
        warnings.warn(f"\nFailed to find {e}")
        return 1

    finally:
        # Clean up the container
        # shutil.rmtree(compiler_root, ignore_errors=True)
        pass


if __name__ == "__main__":
    sys.exit(main())
