# Compile the FastLED library in all three modes using native Python compiler

import argparse
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum


class ArchiveType(Enum):
    """Enum for specifying which archive types to build."""

    THIN = "thin"
    REGULAR = "regular"
    BOTH = "both"


def _build_archives(
    build_mode: str, archive_type: ArchiveType = ArchiveType.THIN
) -> int:
    """Build specified archive types for the given build mode using native Python compiler.

    Args:
        build_mode: One of "debug", "quick", "release"
        archive_type: Which archive types to build (thin, regular, or both)

    Returns:
        0 if successful, non-zero if any build failed
    """
    from fastled_wasm_compiler.native_compile_lib import build_library
    from fastled_wasm_compiler.types import BuildMode

    # Map string to BuildMode enum
    mode_map = {
        "debug": BuildMode.DEBUG,
        "quick": BuildMode.QUICK,
        "release": BuildMode.RELEASE,
    }
    mode = mode_map[build_mode]

    try:
        if archive_type == ArchiveType.THIN:
            print(f"📦 Building thin archive for {build_mode}...")
            archive_path = build_library(
                build_mode=mode,
                use_thin_archive=True,
                max_workers=None,
            )
            print(f"✅ Thin archive built: {archive_path}")
            return 0

        elif archive_type == ArchiveType.REGULAR:
            print(f"📦 Building regular archive for {build_mode}...")
            archive_path = build_library(
                build_mode=mode,
                use_thin_archive=False,
                max_workers=None,
            )
            print(f"✅ Regular archive built: {archive_path}")
            return 0

        elif archive_type == ArchiveType.BOTH:
            print(f"🚀 Building both archive types for {build_mode}...")
            print("⚡ Using compile-once-link-twice strategy")

            # Build thin archive first
            thin_path = build_library(
                build_mode=mode,
                use_thin_archive=True,
                max_workers=None,
            )
            print(f"✅ Thin archive built: {thin_path}")

            # Build regular archive (will reuse object files from cache)
            regular_path = build_library(
                build_mode=mode,
                use_thin_archive=False,
                max_workers=None,
            )
            print(f"✅ Regular archive built: {regular_path}")

            print(f"🎉 Both archive types built successfully for {build_mode}")
            print("✨ Object files compiled once, archives linked separately")
            return 0

    except Exception as e:
        print(f"❌ Native build failed for {build_mode}: {e}")
        import traceback

        traceback.print_exc()
        return 1


@dataclass
class BuildResult:
    return_code: int
    duration: float
    stdout: str


def main():
    """Run all tests with --src and --out options."""
    parser = argparse.ArgumentParser(
        description="Compile FastLED for WASM in all modes"
    )
    parser.add_argument(
        "--src", required=True, help="Source directory path for FastLED"
    )
    parser.add_argument("--out", required=True, help="Output directory path")
    args = parser.parse_args()

    src: str = args.src
    out: str = args.out

    # Use the updated compile_all_libs function
    result = compile_all_libs(src, out)

    if result.return_code == 0:
        print("✅ All builds completed successfully")
    else:
        print(f"❌ Build failed with return code {result.return_code}")

    return result.return_code


def compile_all_libs(
    src: str,
    out: str,
    build_modes: list[str] | None = None,
    archive_type: ArchiveType | None = None,
) -> BuildResult:
    """Compile FastLED libraries for specified build modes.

    Args:
        src: Source directory path
        out: Output directory path
        build_modes: List of build modes to compile
        archive_type: Which archive types to build (thin, regular, or both).
                     If None, uses centralized archive mode detection.
    """
    start_time = time.time()
    build_modes = build_modes or ["debug", "quick", "release"]

    # Use centralized archive mode detection if not explicitly specified
    if archive_type is None:
        from fastled_wasm_compiler.paths import get_archive_build_mode

        archive_mode = get_archive_build_mode()

        if archive_mode == "thin":
            archive_type = ArchiveType.THIN
        elif archive_mode == "regular":
            archive_type = ArchiveType.REGULAR
        else:  # "both" - legacy mode
            archive_type = ArchiveType.BOTH
    else:
        # Validate that passed archive_type matches environment configuration
        from fastled_wasm_compiler.paths import get_archive_build_mode

        archive_mode = get_archive_build_mode()
        expected_archive_type = None

        if archive_mode == "thin":
            expected_archive_type = ArchiveType.THIN
        elif archive_mode == "regular":
            expected_archive_type = ArchiveType.REGULAR
        else:  # "both" - legacy mode
            expected_archive_type = ArchiveType.BOTH

        # Check for mismatch and warn if necessary
        if archive_type != expected_archive_type:
            print("⚠️  WARNING: Archive type mismatch detected!")
            print(f"   Requested: {archive_type.value}")
            print(f"   Environment (ARCHIVE_BUILD_MODE): {archive_mode}")
            print(
                f"   Switching to environment configuration: {expected_archive_type.value}"
            )
            archive_type = expected_archive_type
    build_times: dict[str, float] = OrderedDict()
    captured_stdout: list[str] = []

    for build_mode in build_modes:
        build_start_time = time.time()
        print(f"Building {build_mode} in {out}/{build_mode}...")

        # Build specified archive types for this mode
        result_code = _build_archives(build_mode, archive_type)

        if result_code != 0:
            print(f"❌ Failed to build archives for {build_mode}")
            end_time = time.time()
            elapsed_time = end_time - start_time
            return BuildResult(
                return_code=result_code,
                duration=elapsed_time,
                stdout="".join(captured_stdout),
            )

        diff = time.time() - build_start_time
        build_times[build_mode] = diff

    print("All processes finished successfully.")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken: {elapsed_time:.2f} seconds")
    for mode, duration in build_times.items():
        print(f"  {mode} build time: {duration:.2f} seconds")
    return BuildResult(
        return_code=0, duration=elapsed_time, stdout="".join(captured_stdout)
    )


if __name__ == "__main__":
    sys.exit(main())
