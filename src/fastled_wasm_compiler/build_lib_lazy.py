"""
Lazy library builder with timestamp checking.

This module provides lazy rebuild functionality for FastLED libraries,
only rebuilding when source has changed since the last build.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastled_wasm_compiler.timestamp_utils import get_timestamp_manager

if TYPE_CHECKING:
    pass


def build_library_if_needed(
    build_mode: str, force: bool = False, git_root: Path | None = None
) -> bool:
    """Build library for the specified mode if needed based on timestamps.

    Args:
        build_mode: Build mode (debug, quick, release)
        force: Force rebuild even if timestamps indicate it's not needed
        git_root: Git root directory (defaults to /git)

    Returns:
        True if library was built, False if it was skipped
    """
    build_mode_lower = build_mode.lower()

    if git_root is None:
        git_root = Path("/git")

    timestamp_manager = get_timestamp_manager(git_root)

    print(f"🔍 Checking if {build_mode} library needs rebuilding...")

    # Check both archive types
    needs_thin_rebuild = force or timestamp_manager.should_rebuild_library(
        build_mode_lower, "thin"
    )
    needs_regular_rebuild = force or timestamp_manager.should_rebuild_library(
        build_mode_lower, "regular"
    )

    if not needs_thin_rebuild and not needs_regular_rebuild:
        print(f"⚡ Skipping {build_mode} build - libraries are up to date")
        return False

    # Build is needed
    if force:
        print(f"🔨 Force rebuilding {build_mode} libraries...")
    else:
        if needs_thin_rebuild:
            print(f"🔨 Rebuilding {build_mode} thin library...")
        if needs_regular_rebuild:
            print(f"🔨 Rebuilding {build_mode} regular library...")

    # Run the build script
    build_script = git_root / "fastled-wasm" / ".." / "build_tools" / "build_lib.sh"
    if not build_script.exists():
        build_script = Path("/build/build_lib.sh")

    if not build_script.exists():
        raise RuntimeError(f"Build script not found at {build_script}")

    # Set environment for the build
    env = os.environ.copy()
    env["BUILD_MODE"] = build_mode.upper()

    # Run the build command
    cmd = ["bash", str(build_script), f"--{build_mode_lower}"]

    print(f"🔧 Running: {' '.join(cmd)}")
    try:
        subprocess.run(
            cmd,
            cwd=str(git_root / "fastled-wasm"),
            env=env,
            check=True,
            capture_output=False,  # Let output show in real-time
            text=True,
        )
        print(f"✅ {build_mode} library build completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {build_mode} library build failed with exit code {e.returncode}")
        raise


def build_all_libraries_if_needed(
    build_modes: list[str] | None = None,
    force: bool = False,
    git_root: Path | None = None,
) -> dict[str, bool]:
    """Build all specified libraries if needed based on timestamps.

    Args:
        build_modes: List of build modes to check (defaults to ["debug", "quick", "release"])
        force: Force rebuild even if timestamps indicate it's not needed
        git_root: Git root directory (defaults to /git)

    Returns:
        Dictionary mapping build mode to whether it was built
    """
    if build_modes is None:
        build_modes = ["debug", "quick", "release"]

    results = {}

    for build_mode in build_modes:
        try:
            built = build_library_if_needed(build_mode, force=force, git_root=git_root)
            results[build_mode] = built
        except Exception as e:
            print(f"❌ Failed to build {build_mode}: {e}")
            results[build_mode] = False
            if not force:
                # If not forcing, stop on first failure
                break

    return results


def main() -> int:
    """Main entry point for lazy library building."""
    import argparse

    parser = argparse.ArgumentParser(description="Lazy FastLED library builder")
    parser.add_argument(
        "--debug", action="store_true", help="Build debug library if needed"
    )
    parser.add_argument(
        "--quick", action="store_true", help="Build quick library if needed"
    )
    parser.add_argument(
        "--release", action="store_true", help="Build release library if needed"
    )
    parser.add_argument(
        "--all", action="store_true", help="Build all libraries if needed"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force rebuild even if up to date"
    )
    parser.add_argument(
        "--git-root", type=Path, help="Git root directory (default: /git)"
    )

    args = parser.parse_args()

    # Determine which modes to build
    build_modes = []
    if args.all:
        build_modes = ["debug", "quick", "release"]
    else:
        if args.debug:
            build_modes.append("debug")
        if args.quick:
            build_modes.append("quick")
        if args.release:
            build_modes.append("release")

    if not build_modes:
        # Default to all modes
        build_modes = ["debug", "quick", "release"]

    try:
        results = build_all_libraries_if_needed(
            build_modes=build_modes, force=args.force, git_root=args.git_root
        )

        # Summary
        built_count = sum(1 for built in results.values() if built)
        total_count = len(results)

        print("\n📊 Build Summary:")
        print(f"   Built: {built_count}/{total_count} libraries")
        for mode, built in results.items():
            status = "✅ Built" if built else "⚡ Skipped"
            print(f"   {mode}: {status}")

        return 0
    except Exception as e:
        print(f"❌ Build failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
