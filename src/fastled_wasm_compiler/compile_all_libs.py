# compile the fastled library in all three modes
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/debug --debug
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/quick --quick
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/release --release

import argparse
import subprocess
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


def _get_cmd(build: str) -> list[str]:
    """Get the command to run based on the build mode."""
    assert build in ["debug", "quick", "release"], f"Invalid build mode: {build}"
    cmd_list: list[str] = [
        "/build/build_lib.sh",
        f"--{build}",
    ]
    return cmd_list


def _build_archives(
    build_mode: str, archive_type: ArchiveType = ArchiveType.THIN
) -> int:
    """Build specified archive types for the given build mode.

    Args:
        build_mode: One of "debug", "quick", "release"
        archive_type: Which archive types to build (thin, regular, or both)

    Returns:
        0 if successful, non-zero if any build failed
    """
    import os

    cmd = _get_cmd(build_mode)

    if archive_type == ArchiveType.THIN:
        print(f"📦 Building thin archives for {build_mode}...")
        env_thin = os.environ.copy()
        env_thin["NO_THIN_LTO"] = "0"

        result = subprocess.run(
            cmd,
            env=env_thin,
            cwd="/git/fastled-wasm",
            capture_output=False,  # Always show output in real-time
            text=True,
        )
        if result.returncode != 0:
            print(f"❌ Failed to build thin archives for {build_mode}")
            return result.returncode
        print(f"✅ Thin archives built successfully for {build_mode}")

    elif archive_type == ArchiveType.REGULAR:
        print(f"📦 Building regular archives for {build_mode}...")
        env_regular = os.environ.copy()
        env_regular["NO_THIN_LTO"] = "1"

        result = subprocess.run(
            cmd,
            env=env_regular,
            cwd="/git/fastled-wasm",
            capture_output=False,  # Always show output in real-time
            text=True,
        )
        if result.returncode != 0:
            print(f"❌ Failed to build regular archives for {build_mode}")
            return result.returncode
        print(f"✅ Regular archives built successfully for {build_mode}")

    elif archive_type == ArchiveType.BOTH:
        print(f"🚀 Building both archive types for {build_mode} mode...")
        print("⚡ Using optimized compile-once-link-twice strategy")

        # The optimized build_lib.sh script now handles building both archive types
        # in a single invocation using the compile-once-link-twice pattern:
        # 1. Compile object files once (NO_LINK=ON)
        # 2. Link thin archive (NO_BUILD=ON, NO_THIN_LTO=0)
        # 3. Link regular archive (NO_BUILD=ON, NO_THIN_LTO=1)

        # No need to set NO_THIN_LTO here - the script manages it internally
        env = os.environ.copy()
        # Remove any existing NO_THIN_LTO to let the script control it
        env.pop("NO_THIN_LTO", None)

        result = subprocess.run(
            cmd,
            env=env,
            cwd="/git/fastled-wasm",
            capture_output=False,  # Always show output in real-time
            text=True,
        )
        if result.returncode != 0:
            print(f"❌ Failed to build archives for {build_mode}")
            return result.returncode

        print(f"🎉 Both archive types built successfully for {build_mode}")
        print("✨ Object files compiled once, archives linked separately")

    return 0


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
