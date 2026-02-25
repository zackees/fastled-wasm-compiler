#!/usr/bin/env python3
"""
Native library compiler for FastLED WASM.

This module provides a pure Python build system using FastLED's
proven native compiler infrastructure.
"""

import multiprocessing
import os
import shutil
import time
from concurrent.futures import Future
from pathlib import Path
from typing import List, Tuple

from .build_flags_adapter import load_wasm_compiler_flags
from .native_compiler import (
    Compiler,
    CompilerOptions,
    LibarchiveOptions,
    Result,
)
from .paths import BUILD_ROOT, get_fastled_source_path
from .types import BuildMode


def find_emscripten_tool(tool_name: str) -> str:
    """
    Find Emscripten tool (emcc, emar, etc.) in PATH or emsdk.

    Args:
        tool_name: Name of tool (emcc, emar, etc.)

    Returns:
        Full path to tool or just tool_name if in PATH

    Raises:
        RuntimeError: If tool not found
    """
    # First check if it's in PATH
    if shutil.which(tool_name):
        return tool_name

    # On Windows, we need the .bat wrapper for Python scripts
    is_windows = os.name == "nt" or os.environ.get("OS", "").lower() == "windows_nt"

    # Check common emsdk locations
    home = Path.home()
    emsdk_locations = [
        (
            home / "emsdk" / "upstream" / "emscripten" / f"{tool_name}.bat"
            if is_windows
            else home / "emsdk" / "upstream" / "emscripten" / tool_name
        ),
        home / "emsdk" / "upstream" / "emscripten" / tool_name,
        Path("/emsdk/upstream/emscripten") / tool_name,  # Docker location
    ]

    for path in emsdk_locations:
        if path.exists():
            return str(path)

    # Last resort: try environment variable
    emsdk_root = os.environ.get("EMSDK")
    if emsdk_root:
        emsdk_tool = (
            Path(emsdk_root) / "upstream" / "emscripten" / f"{tool_name}.bat"
            if is_windows
            else Path(emsdk_root) / "upstream" / "emscripten" / tool_name
        )
        if emsdk_tool.exists():
            return str(emsdk_tool)

    raise RuntimeError(
        f"{tool_name} not found. Please install emsdk or add it to PATH.\n"
        + "Tried: PATH, ~/emsdk, /emsdk, $EMSDK"
    )


class NativeLibraryBuilder:
    """
    Builds libfastled.a using native Python compiler.

    This class uses direct compiler invocations via FastLED's native_compiler module.
    """

    def __init__(
        self,
        build_mode: BuildMode,
        use_thin_archive: bool = False,
        max_workers: int | None = None,
    ):
        """
        Initialize native library builder.

        Args:
            build_mode: Debug, Quick, or Release
            use_thin_archive: Create thin archive for faster linking
            max_workers: Number of parallel workers (default: CPU count * 2)
        """
        self.build_mode = build_mode
        self.use_thin_archive = use_thin_archive
        self.max_workers = max_workers or (multiprocessing.cpu_count() * 2)

        # Build directory
        self.build_dir = BUILD_ROOT / build_mode.name.lower()
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # FastLED source directory
        self.fastled_src = Path(get_fastled_source_path())

        # Load build flags from TOML
        toml_path = Path(__file__).parent / "build_flags.toml"
        self.build_flags = load_wasm_compiler_flags(
            toml_path, build_mode=build_mode.name.lower()
        )

        # Find Emscripten tools
        emcc_path = find_emscripten_tool("emcc")
        emar_path = find_emscripten_tool("emar")

        # Update build_flags with full paths to tools
        self.build_flags.tools.archiver = [emar_path]

        # Create compiler settings
        # IMPORTANT: compiler_args must start with the compiler command for native_compiler
        # It expects compiler_args to be the full command: ["emcc", ...flags]
        compiler_args_with_cmd = [emcc_path] + self.build_flags.compiler_flags

        self.settings = CompilerOptions(
            include_path=str(self.fastled_src),
            compiler=emcc_path,  # Not used directly, compiler_args takes precedence
            defines=self.build_flags.defines,
            std_version="gnu++17",
            compiler_args=compiler_args_with_cmd,
            use_pch=True,
            pch_header_content=self._generate_pch_content(),
            pch_output_path=str(self.build_dir / "fastled_pch.h.gch"),
            archiver=emar_path,
            archiver_args=[],
            parallel=True,
        )

        # Create compiler instance
        self.compiler = Compiler(self.settings, self.build_flags)

        print("🔧 Initialized NativeLibraryBuilder:")
        print(f"   Mode: {build_mode.name}")
        print(f"   Build dir: {self.build_dir}")
        print(f"   Thin archive: {use_thin_archive}")
        print(f"   Workers: {self.max_workers}")

    def _generate_pch_content(self) -> str:
        """Generate PCH header content for WASM."""
        return """// FastLED WASM PCH - Precompiled header for faster compilation
#pragma once

// Core Arduino compatibility
#include <Arduino.h>

// FastLED main header
#include <FastLED.h>

// Common standard library headers
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Emscripten headers
#include <emscripten.h>
#include <emscripten/bind.h>
"""

    def _discover_source_files(self) -> List[Path]:
        """
        Discover all FastLED source files to compile.

        Includes all .cpp files in src/ without platform filtering.
        Unity build handles file inclusion automatically via _build.cpp files.

        Returns:
            List of .cpp files to compile
        """
        all_cpp_files = list(self.fastled_src.rglob("*.cpp"))

        print(f"📂 Discovered {len(all_cpp_files)} source files:")
        for f in sorted(all_cpp_files)[:10]:  # Show first 10
            print(f"   - {f.relative_to(self.fastled_src)}")
        if len(all_cpp_files) > 10:
            print(f"   ... and {len(all_cpp_files) - 10} more")

        return all_cpp_files

    def _compile_all_sources(
        self, source_files: List[Path]
    ) -> Tuple[List[Path], List[str]]:
        """
        Compile all source files in parallel.

        Args:
            source_files: List of .cpp files to compile

        Returns:
            Tuple of (object_files, error_messages)
        """
        print(f"\n🔨 Compiling {len(source_files)} source files...")
        start_time = time.time()

        futures: List[Tuple[Future, Path, Path]] = []

        for src_file in source_files:
            # Create object file path
            relative_path = src_file.relative_to(self.fastled_src)
            safe_name = (
                str(relative_path.with_suffix("")).replace("/", "_").replace("\\", "_")
            )
            obj_path = self.build_dir / f"{safe_name}.o"

            # Submit compilation
            future = self.compiler.compile_cpp_file(
                src_file,
                output_path=obj_path,
                additional_flags=["-c"],  # Compile only, don't link
            )
            futures.append((future, obj_path, src_file))

        # Wait for all compilations
        object_files = []
        errors = []
        succeeded = 0
        failed = 0

        for future, obj_path, src_file in futures:
            result: Result = future.result()
            if result.ok:
                object_files.append(obj_path)
                succeeded += 1
            else:
                failed += 1
                error_msg = f"Failed to compile {src_file.name}:\n{result.stderr}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")

        elapsed = time.time() - start_time
        print("\n✅ Compilation complete:")
        print(f"   Succeeded: {succeeded}/{len(source_files)}")
        print(f"   Failed: {failed}/{len(source_files)}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Rate: {len(source_files)/elapsed:.1f} files/sec")

        return object_files, errors

    def _create_archive(self, object_files: List[Path]) -> Path:
        """
        Create static library archive from object files.

        Args:
            object_files: List of .o files

        Returns:
            Path to created archive

        Raises:
            RuntimeError: If archive creation fails
        """
        archive_name = "libfastled-thin.a" if self.use_thin_archive else "libfastled.a"
        output_archive = self.build_dir / archive_name

        print(f"\n📦 Creating archive: {archive_name}")
        print(f"   Object files: {len(object_files)}")
        print(f"   Archive type: {'thin' if self.use_thin_archive else 'regular'}")

        archive_options = LibarchiveOptions(use_thin=self.use_thin_archive)

        start_time = time.time()

        archive_future = self.compiler.create_archive(
            object_files, output_archive, archive_options
        )

        result: Result = archive_future.result()
        elapsed = time.time() - start_time

        if not result.ok:
            raise RuntimeError(f"Archive creation failed:\n{result.stderr}")

        # Verify archive was created
        if not output_archive.exists():
            raise RuntimeError(f"Archive file not found: {output_archive}")

        archive_size = output_archive.stat().st_size
        print("✅ Archive created successfully:")
        print(f"   Path: {output_archive}")
        print(f"   Size: {archive_size:,} bytes ({archive_size / 1024 / 1024:.2f} MB)")
        print(f"   Time: {elapsed:.2f}s")

        return output_archive

    def build(self) -> Path:
        """
        Build libfastled.a and return path to archive.

        This is the main entry point that orchestrates:
        1. PCH generation
        2. Source file discovery
        3. Parallel compilation
        4. Archive creation

        Returns:
            Path to built library archive

        Raises:
            RuntimeError: If build fails
        """
        print("\n" + "=" * 70)
        print(f"🚀 Building FastLED Library ({self.build_mode.name} mode)")
        print("=" * 70)

        build_start_time = time.time()

        # Step 1: Generate PCH
        print("\n📋 Step 1/4: Generating precompiled header...")
        pch_success = self.compiler.create_pch_file()
        if pch_success:
            print("✅ PCH generated successfully")
        else:
            print("⚠️  PCH generation failed, continuing without PCH")

        # Step 2: Discover source files
        print("\n📋 Step 2/4: Discovering source files...")
        source_files = self._discover_source_files()

        if not source_files:
            raise RuntimeError("No source files found!")

        # Step 3: Compile all sources
        print("\n📋 Step 3/4: Compiling source files...")
        object_files, errors = self._compile_all_sources(source_files)

        if errors:
            raise RuntimeError(
                f"Compilation failed with {len(errors)} errors:\n"
                + "\n".join(errors[:5])  # Show first 5 errors
            )

        # Step 4: Create archive
        print("\n📋 Step 4/4: Creating static library archive...")
        archive_path = self._create_archive(object_files)

        # Summary
        total_time = time.time() - build_start_time
        print("\n" + "=" * 70)
        print("🎉 BUILD SUCCESSFUL")
        print("=" * 70)
        print(f"Archive: {archive_path}")
        print(f"Total time: {total_time:.2f}s")
        print("=" * 70 + "\n")

        return archive_path


def build_library(
    build_mode: BuildMode,
    use_thin_archive: bool = False,
    max_workers: int | None = None,
) -> Path:
    """
    Build FastLED library for WASM using native Python compiler.

    Args:
        build_mode: Debug, Quick, or Release
        use_thin_archive: Create thin archive for faster linking
        max_workers: Number of parallel workers

    Returns:
        Path to built library archive
    """
    builder = NativeLibraryBuilder(build_mode, use_thin_archive, max_workers)
    return builder.build()


def main() -> int:
    """CLI entry point for building library."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Build FastLED WASM library using Python native compiler"
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--debug", action="store_true", help="Debug mode")
    mode_group.add_argument("--quick", action="store_true", help="Quick mode")
    mode_group.add_argument("--release", action="store_true", help="Release mode")
    parser.add_argument("--thin", action="store_true", help="Create thin archive")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: CPU count * 2)",
    )

    args = parser.parse_args()

    if args.debug:
        mode = BuildMode.DEBUG
    elif args.quick:
        mode = BuildMode.QUICK
    elif args.release:
        mode = BuildMode.RELEASE
    else:
        print("Error: Must specify build mode", file=sys.stderr)
        return 1

    try:
        archive_path = build_library(
            build_mode=mode,
            use_thin_archive=args.thin,
            max_workers=args.workers,
        )
        print(f"\n✅ Success: {archive_path}")
        return 0
    except Exception as e:
        print(f"\n❌ Build failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
