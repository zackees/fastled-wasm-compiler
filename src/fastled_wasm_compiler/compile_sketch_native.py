"""
Native EMSDK Compilation Module

This module provides compilation functionality using locally installed EMSDK
instead of Docker containers. This is part of the migration from Docker-based
compilation to native compilation using pre-built EMSDK binaries.

Key differences from compile_sketch.py:
- Uses EmsdkManager for tool path resolution
- Sets up local environment instead of container environment
- Downloads and manages EMSDK automatically
- Cross-platform compatible (Windows, macOS, Linux)
"""

import argparse
import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler import paths
from fastled_wasm_compiler.compilation_flags import get_compilation_flags
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
from fastled_wasm_compiler.fastled_downloader import ensure_fastled_installed


class NativeCompilerImpl:
    """Native EMSDK-based compiler for FastLED sketches."""

    def __init__(self, emsdk_install_dir: Path | None = None) -> None:
        """Initialize native compiler.

        Args:
            emsdk_install_dir: Custom EMSDK installation directory
        """
        self.emsdk_manager = get_emsdk_manager(emsdk_install_dir)
        # Ensure FastLED is installed and get the actual source path
        self.fastled_src = ensure_fastled_installed()

        # Initialize centralized flags system
        self.flags_loader = get_compilation_flags()

    def get_compilation_flags(
        self, build_mode: str, strict_mode: bool = False
    ) -> list[str]:
        """Get compilation flags for the specified build mode using centralized configuration."""
        flags = self.flags_loader.get_full_compilation_flags(
            compilation_type="sketch",
            build_mode=build_mode,
            fastled_src_path=self.fastled_src.as_posix(),
            strict_mode=strict_mode,
        )

        # Add native-specific flags that aren't in the centralized config
        native_specific_flags = [
            "-DFASTLED_ALL_SRC=1",  # Enable unified FastLED compilation for native builds
        ]

        # Add Thin PCH support if enabled
        if os.environ.get("THIN_PCH") == "1":
            # For Thin PCH, we need to include the PCH header
            build_dir = os.environ.get("BUILD_DIR", "/tmp/fastled-build")
            pch_header_path = f"{build_dir}/fastled_pch.h"
            if os.path.exists(pch_header_path):
                native_specific_flags.extend(["-include", pch_header_path])

        return native_specific_flags + flags

    def get_linking_flags(self, build_mode: str) -> list[str]:
        """Get linking flags for the specified build mode using centralized configuration."""
        linker = os.environ.get("LINKER", "lld")
        return self.flags_loader.get_full_linking_flags(
            compilation_type="sketch",
            linker=linker,
            build_mode=build_mode,
        )

    def ensure_emsdk(self) -> None:
        """Ensure EMSDK is installed and ready."""
        if not self.emsdk_manager.is_installed():
            print("EMSDK not found, installing...")
            self.emsdk_manager.install()

        print(f"Using EMSDK at: {self.emsdk_manager.emsdk_dir}")

    def get_compilation_env(self) -> dict[str, str]:
        """Get environment variables for compilation."""
        return self.emsdk_manager.setup_environment()

    def get_tool_paths(self) -> dict[str, Path]:
        """Get paths to compilation tools."""
        return self.emsdk_manager.get_tool_paths()

    def compile_source_to_object(
        self, source_file: Path, build_mode: str, build_dir: Path
    ) -> Path:
        """Compile a single source file to object file.

        Args:
            source_file: Source file to compile
            build_mode: Build mode (debug, quick, release)
            build_dir: Directory for build outputs

        Returns:
            Path to generated object file
        """
        self.ensure_emsdk()

        # Set up build directory
        build_dir.mkdir(parents=True, exist_ok=True)

        # Generate object file path
        obj_file = build_dir / f"{source_file.stem}.o"

        # Get compilation flags
        flags = self.get_compilation_flags(build_mode)

        # Get tool paths and environment
        tool_paths = self.get_tool_paths()
        env = self.get_compilation_env()

        # Build compilation command
        cmd = [
            str(tool_paths["em++"]),
            "-c",
            "-x",
            "c++",
            "-o",
            str(obj_file),
            *flags,
            str(source_file),
        ]

        print(
            f"Compiling {source_file.name}: {' '.join(cmd[:3])} ... {source_file.name}"
        )

        # Run compilation
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Compilation failed for {source_file}:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise RuntimeError(f"Failed to compile {source_file}: {result.stderr}")

        if not obj_file.exists():
            raise RuntimeError(f"Object file not created: {obj_file}")

        print(f"Compiled {source_file.name} -> {obj_file.name}")
        return obj_file

    def link_objects_to_wasm(
        self,
        object_files: list[Path],
        build_mode: str,
        output_dir: Path,
        fastled_lib_path: Path | None = None,
        output_name: str = "fastled",
    ) -> Path:
        """Link object files into WASM module.

        Args:
            object_files: List of object files to link
            build_mode: Build mode (debug, quick, release)
            output_dir: Directory for output files
            fastled_lib_path: Path to pre-built FastLED library (required for sketch compilation)
            output_name: Base name for output files

        Returns:
            Path to generated JavaScript file
        """
        self.ensure_emsdk()

        # Set up output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output paths
        js_file = output_dir / f"{output_name}.js"
        wasm_file = output_dir / f"{output_name}.wasm"

        # Get linker flags
        link_flags = self.get_linking_flags(build_mode)

        # Add debug-specific DWARF file generation for debug mode
        if build_mode.lower() == "debug":
            dwarf_file = output_dir / f"{output_name}.wasm.dwarf"
            link_flags.append(f"-gseparate-dwarf={dwarf_file}")

        # Get tool paths and environment
        tool_paths = self.get_tool_paths()
        env = self.get_compilation_env()

        # Build linking command with sketch objects + FastLED library
        cmd = [
            str(tool_paths["em++"]),
            *link_flags,
            "-o",
            str(js_file),
            *[str(obj) for obj in object_files],
        ]

        # Add pre-built FastLED library if provided
        if fastled_lib_path:
            cmd.append(str(fastled_lib_path))
            print(
                f"Linking {len(object_files)} sketch objects + FastLED library to {js_file.name}"
            )
            print(f"📚 Using FastLED library: {fastled_lib_path}")
        else:
            print(f"Linking {len(object_files)} objects to {js_file.name}")

        # Run linking
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            print("Linking failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise RuntimeError(f"Failed to link: {result.stderr}")

        if not js_file.exists():
            raise RuntimeError(f"JavaScript file not created: {js_file}")

        if not wasm_file.exists():
            raise RuntimeError(f"WASM file not created: {wasm_file}")

        print(f"✅ Successfully linked: {js_file}")
        print(f"✅ WASM module: {wasm_file}")

        return js_file

    def compile_sketch(
        self, sketch_dir: Path, build_mode: str, output_dir: Path | None = None
    ) -> Path:
        """Compile a complete FastLED sketch.

        Args:
            sketch_dir: Directory containing sketch source files
            build_mode: Build mode (debug, quick, release)
            output_dir: Output directory (defaults to sketch_dir/fastled_js)

        Returns:
            Path to generated JavaScript file
        """
        if output_dir is None:
            output_dir = sketch_dir / "fastled_js"

        # Find source files
        source_files = []
        for pattern in ["*.cpp", "*.ino"]:
            source_files.extend(sketch_dir.glob(pattern))

        if not source_files:
            raise RuntimeError(f"No source files found in {sketch_dir}")

        print(f"Found {len(source_files)} sketch source files in {sketch_dir}")

        # Find pre-built FastLED library to link against using centralized logic
        fastled_lib_path = paths.get_fastled_library_path(build_mode)
        archive_type = "thin" if "thin" in fastled_lib_path.name else "regular"

        print(f"🎯 Total files to compile: {len(source_files)} (sketch files only)")
        print(f"📚 FastLED library: {fastled_lib_path} ({archive_type})")

        # Create build directory
        build_dir = output_dir / "build" / build_mode.lower()
        build_dir.mkdir(parents=True, exist_ok=True)

        # Compile sketch source files only (not FastLED)
        object_files = []
        for source_file in source_files:
            obj_file = self.compile_source_to_object(source_file, build_mode, build_dir)
            object_files.append(obj_file)

        # Link sketch objects + pre-built FastLED library to WASM
        js_file = self.link_objects_to_wasm(
            object_files, build_mode, output_dir, fastled_lib_path
        )

        return js_file


def compile_sketch_native(
    sketch_dir: Path,
    build_mode: str = "debug",
    output_dir: Path | None = None,
    emsdk_install_dir: Path | None = None,
) -> Path:
    """Convenience function to compile a sketch using native EMSDK.

    Args:
        sketch_dir: Directory containing sketch source files
        build_mode: Build mode (debug, quick, release)
        output_dir: Output directory (defaults to sketch_dir/fastled_js)
        emsdk_install_dir: Custom EMSDK installation directory

    Returns:
        Path to generated JavaScript file
    """
    compiler = NativeCompilerImpl(emsdk_install_dir)
    return compiler.compile_sketch(sketch_dir, build_mode, output_dir)


def main():
    """Command line interface for native compilation."""
    parser = argparse.ArgumentParser(
        description="Compile FastLED sketches using native EMSDK"
    )

    parser.add_argument(
        "sketch_dir", type=Path, help="Directory containing sketch source files"
    )

    parser.add_argument(
        "--mode",
        choices=["debug", "quick", "release"],
        default="debug",
        help="Build mode (default: debug)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: sketch_dir/fastled_js)",
    )

    parser.add_argument(
        "--emsdk-dir", type=Path, help="Custom EMSDK installation directory"
    )

    parser.add_argument(
        "--install-emsdk", action="store_true", help="Install EMSDK if not present"
    )

    args = parser.parse_args()

    try:
        # Validate sketch directory
        if not args.sketch_dir.exists():
            raise RuntimeError(f"Sketch directory not found: {args.sketch_dir}")

        # Install EMSDK if requested
        if args.install_emsdk:
            manager = get_emsdk_manager(args.emsdk_dir)
            manager.install()
            print("EMSDK installation complete")
            return 0

        # Compile sketch
        print(f"Compiling sketch: {args.sketch_dir}")
        print(f"Build mode: {args.mode}")

        js_file = compile_sketch_native(
            sketch_dir=args.sketch_dir,
            build_mode=args.mode,
            output_dir=args.output_dir,
            emsdk_install_dir=args.emsdk_dir,
        )

        print("\n✅ Compilation successful!")
        print(f"Output: {js_file}")
        print(f"WASM: {js_file.with_suffix('.wasm')}")

        return 0

    except Exception as e:
        print(f"\n❌ Compilation failed: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
