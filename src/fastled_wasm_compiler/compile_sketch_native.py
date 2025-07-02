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
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
from fastled_wasm_compiler.fastled_downloader import ensure_fastled_installed


class NativeCompilerImpl:
    """Native EMSDK-based compiler for FastLED sketches."""

    def __init__(self, emsdk_install_dir: Optional[Path] = None):
        """Initialize native compiler.

        Args:
            emsdk_install_dir: Custom EMSDK installation directory
        """
        self.emsdk_manager = get_emsdk_manager(emsdk_install_dir)
        # Ensure FastLED is installed and get the actual source path
        self.fastled_src = ensure_fastled_installed()

        # Base compilation flags - removed manual __EMSCRIPTEN__ definition
        # emcc should define this automatically when using Emscripten
        self.base_flags = [
            "-UFASTLED_ALL_SRC",  # Undefine FASTLED_ALL_SRC to enable individual file compilation
            "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
            "-DFASTLED_FORCE_NAMESPACE=1",
            "-DFASTLED_USE_PROGMEM=0",
            "-DUSE_OFFSET_CONVERTER=0",
            "-DSKETCH_COMPILE=1",
            "-DFASTLED_WASM_USE_CCALL",
            "-DGL_ENABLE_GET_PROC_ADDRESS=0",
            "-std=gnu++17",
            "-fpermissive",
            "-Wno-constant-logical-operand",
            "-Wnon-c-typedef-for-linkage",
            "-Werror=bad-function-cast",
            "-Werror=cast-function-type",
            # Threading disabled flags
            "-fno-threadsafe-statics",  # Disable thread-safe static initialization
            "-DEMSCRIPTEN_NO_THREADS",  # Define to disable threading
            "-D_REENTRANT=0",  # Disable reentrant code
            "-I.",
            "-Isrc",
            f"-I{self.fastled_src.as_posix()}",
            f"-I{self.fastled_src.as_posix()}/platforms/wasm/compiler",
        ]

        # Debug-specific flags
        self.debug_flags = [
            "-g3",
            "-gsource-map",
            "-ffile-prefix-map=/=sketchsource/",
            "-fsanitize=address",
            "-fsanitize=undefined",
            "-fno-inline",
            "-O0",
        ]

        # Quick build flags
        self.quick_flags = [
            "-flto=thin",
            "-O0",
            "-sASSERTIONS=0",
            "-g0",
            "-fno-inline-functions",
            "-fno-vectorize",
            "-fno-unroll-loops",
            "-fno-strict-aliasing",
        ]

        # Release flags
        self.release_flags = [
            "-Oz",
            "-DNDEBUG",
            "-ffunction-sections",
            "-fdata-sections",
        ]

        # Base linker flags
        self.base_link_flags = [
            "-fuse-ld=lld",
            "-sWASM=1",
            "--no-entry",
            "--emit-symbol-map",
            "-sMODULARIZE=1",
            "-sEXPORT_NAME=fastled",
            "-sUSE_PTHREADS=0",
            "-sEXIT_RUNTIME=0",
            "-sALLOW_MEMORY_GROWTH=1",
            "-sINITIAL_MEMORY=134217728",
            "-sAUTO_NATIVE_LIBRARIES=0",
            "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8','HEAPU8','getValue']",
            "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files','_getStripPixelData']",
            "-sFILESYSTEM=0",
            "-Wl,--whole-archive",
            "--source-map-base=http://localhost:8000/",
        ]

        # Debug linker flags
        self.debug_link_flags = [
            "-fsanitize=address",
            "-fsanitize=undefined",
            "-sSEPARATE_DWARF_URL=fastled.wasm.dwarf",
            "-sSTACK_OVERFLOW_CHECK=2",
            "-sASSERTIONS=1",
        ]

    def ensure_emsdk(self) -> None:
        """Ensure EMSDK is installed and ready."""
        if not self.emsdk_manager.is_installed():
            print("EMSDK not found, installing...")
            self.emsdk_manager.install()

        print(f"Using EMSDK at: {self.emsdk_manager.emsdk_dir}")

    def get_compilation_env(self) -> Dict[str, str]:
        """Get environment variables for compilation."""
        return self.emsdk_manager.setup_environment()

    def get_tool_paths(self) -> Dict[str, Path]:
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
        flags = self.base_flags.copy()
        if build_mode.lower() == "debug":
            flags.extend(self.debug_flags)
        elif build_mode.lower() == "quick":
            flags.extend(self.quick_flags)
        elif build_mode.lower() == "release":
            flags.extend(self.release_flags)
        else:
            raise ValueError(f"Unknown build mode: {build_mode}")

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
        object_files: List[Path],
        build_mode: str,
        output_dir: Path,
        output_name: str = "fastled",
    ) -> Path:
        """Link object files into WASM module.

        Args:
            object_files: List of object files to link
            build_mode: Build mode (debug, quick, release)
            output_dir: Directory for output files
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
        link_flags = self.base_link_flags.copy()
        if build_mode.lower() == "debug":
            link_flags.extend(self.debug_link_flags)
            # Add separate DWARF file for debug mode
            dwarf_file = output_dir / f"{output_name}.wasm.dwarf"
            link_flags.append(f"-gseparate-dwarf={dwarf_file}")

        # Get tool paths and environment
        tool_paths = self.get_tool_paths()
        env = self.get_compilation_env()

        # Build linking command
        cmd = [
            str(tool_paths["em++"]),
            *link_flags,
            "-o",
            str(js_file),
            *[str(obj) for obj in object_files],
        ]

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
        self, sketch_dir: Path, build_mode: str, output_dir: Optional[Path] = None
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

        print(f"Found {len(source_files)} source files in {sketch_dir}")

        # Add required WASM platform files from FastLED
        wasm_platform_files = [
            self.fastled_src / "platforms" / "wasm" / "js.cpp",
            self.fastled_src / "platforms" / "wasm" / "js_bindings.cpp",
            self.fastled_src / "platforms" / "wasm" / "active_strip_data.cpp",
            self.fastled_src / "platforms" / "wasm" / "engine_listener.cpp",
            self.fastled_src / "platforms" / "wasm" / "fastspi_wasm.cpp",
            self.fastled_src / "platforms" / "wasm" / "fs_wasm.cpp",
            self.fastled_src / "platforms" / "wasm" / "timer.cpp",
            self.fastled_src / "platforms" / "wasm" / "ui.cpp",
        ]

        # Add core FastLED source files needed for compilation
        core_fastled_files = [
            self.fastled_src / "FastLED.cpp",
            self.fastled_src / "bitswap.cpp",
            self.fastled_src / "cled_controller.cpp",
            self.fastled_src / "colorpalettes.cpp",
            self.fastled_src / "crgb.cpp",
            self.fastled_src / "hsv2rgb.cpp",
            self.fastled_src / "lib8tion.cpp",
            self.fastled_src / "noise.cpp",
            self.fastled_src / "platforms.cpp",
            self.fastled_src / "power_mgt.cpp",
            self.fastled_src / "rgbw.cpp",
            self.fastled_src / "simplex.cpp",
            self.fastled_src / "transpose8x1_noinline.cpp",
            self.fastled_src / "wiring.cpp",
        ]

        # Only add files that exist
        for wasm_file in wasm_platform_files + core_fastled_files:
            if wasm_file.exists():
                source_files.append(wasm_file)
                print(f"Added FastLED file: {wasm_file.name}")

        # Create build directory
        build_dir = output_dir / "build" / build_mode.lower()
        build_dir.mkdir(parents=True, exist_ok=True)

        # Compile all source files
        object_files = []
        for source_file in source_files:
            obj_file = self.compile_source_to_object(source_file, build_mode, build_dir)
            object_files.append(obj_file)

        # Link to WASM
        js_file = self.link_objects_to_wasm(object_files, build_mode, output_dir)

        return js_file


def compile_sketch_native(
    sketch_dir: Path,
    build_mode: str = "debug",
    output_dir: Optional[Path] = None,
    emsdk_install_dir: Optional[Path] = None,
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
