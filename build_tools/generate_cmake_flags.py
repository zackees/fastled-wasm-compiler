#!/usr/bin/env python3
"""
Generate CMake variables from centralized build_flags.toml.
This ensures CMakeLists.txt uses the same flags as sketch compilation.

Fallback order:
1. src/platforms/wasm/compile/build_flags.toml (in FastLED source tree)
2. src/fastled_wasm_compiler/build_flags.toml (fallback)
"""

import sys
import os
from pathlib import Path

# Require tomli - fail if not available
try:
    import tomli
except ImportError:
    print("FATAL ERROR: tomli module is required but not installed.", file=sys.stderr)
    print("Install it with: pip3 install tomli", file=sys.stderr)
    print("This is a controlled environment - dependencies must be explicit.", file=sys.stderr)
    sys.exit(1)


def get_fastled_source_path() -> str:
    """Get the FastLED source path for path resolution."""
    return os.environ.get("ENV_FASTLED_SOURCE_PATH", "/git/fastled/src")


def find_toml_file() -> Path:
    """Find the build_flags.toml file with fallback logic."""
    print("# 🔍 BUILD_FLAGS CMAKE: Searching for build_flags.toml configuration", file=sys.stderr)
    
    # Try FastLED source tree first
    try:
        fastled_src_path = Path(get_fastled_source_path())
        fastled_build_flags = fastled_src_path / "platforms" / "wasm" / "compile" / "build_flags.toml"
        
        print(f"# 📍 BUILD_FLAGS CMAKE: Checking primary location: {fastled_build_flags}", file=sys.stderr)
        
        if fastled_build_flags.exists():
            print(f"# ✅ BUILD_FLAGS CMAKE: Using primary FastLED source config: {fastled_build_flags}", file=sys.stderr)
            return fastled_build_flags
        else:
            print(f"# ⚠️  BUILD_FLAGS CMAKE: Primary config not found at {fastled_build_flags}", file=sys.stderr)
            print("# ⚠️  BUILD_FLAGS CMAKE: This is expected when using Docker/standalone builds", file=sys.stderr)
            
    except Exception as e:
        print(f"# ⚠️  BUILD_FLAGS CMAKE: Error checking FastLED source tree: {e}", file=sys.stderr)
    
    # Fallback to several possible locations for the local build_flags.toml
    possible_paths = [
        # Docker container paths
        Path("/tmp/fastled-wasm-compiler-install/src/fastled_wasm_compiler/build_flags.toml"),
        # Local development paths
        Path(__file__).parent.parent / "src" / "fastled_wasm_compiler" / "build_flags.toml",
        # Relative paths
        Path("src/fastled_wasm_compiler/build_flags.toml"),
        Path("../src/fastled_wasm_compiler/build_flags.toml"),
    ]
    
    print("# 🔄 BUILD_FLAGS CMAKE: Falling back to package resource locations", file=sys.stderr)
    for path in possible_paths:
        if path.exists():
            print(f"# ✅ BUILD_FLAGS CMAKE: Using fallback config: {path}", file=sys.stderr)
            print("# ℹ️  BUILD_FLAGS CMAKE: Using default compiler flags (normal for Docker builds)", file=sys.stderr)
            return path
    
    print(f"# ❌ BUILD_FLAGS CMAKE ERROR: Could not find build_flags.toml in any location:", file=sys.stderr)
    for path in possible_paths:
        print(f"#   - {path}", file=sys.stderr)
    sys.exit(1)


def print_config_status(config: dict, file_path: Path) -> None:
    """Print status of the loaded configuration."""
    print(f"# 📋 BUILD_FLAGS CMAKE: Configuration loaded from {file_path}", file=sys.stderr)
    
    try:
        # Count items in each section
        base_defines = len(config.get("all", {}).get("defines", []))
        base_flags = len(config.get("all", {}).get("compiler_flags", []))
        sketch_defines = len(config.get("sketch", {}).get("defines", []))
        sketch_flags = len(config.get("sketch", {}).get("compiler_flags", []))
        library_defines = len(config.get("library", {}).get("defines", []))
        library_flags = len(config.get("library", {}).get("compiler_flags", []))
        
        # Build modes
        build_modes = list(config.get("build_modes", {}).keys())
        linking_modes = list(config.get("linking", {}).keys())
        
        print(f"#   🔧 Universal defines: {base_defines}", file=sys.stderr)
        print(f"#   🔧 Universal compiler flags: {base_flags}", file=sys.stderr)
        print(f"#   📝 Sketch-specific defines: {sketch_defines}", file=sys.stderr)
        print(f"#   📝 Sketch-specific flags: {sketch_flags}", file=sys.stderr)
        print(f"#   📚 Library-specific defines: {library_defines}", file=sys.stderr)
        print(f"#   📚 Library-specific flags: {library_flags}", file=sys.stderr)
        print(f"#   🎯 Build modes: {', '.join(build_modes)}", file=sys.stderr)
        print(f"#   🔗 Linking modes: {', '.join(linking_modes)}", file=sys.stderr)
        
        # Total for CMake generation
        total_cmake_flags = base_defines + base_flags + library_defines + library_flags
        print(f"#   📦 Total CMake flags to generate: {total_cmake_flags}", file=sys.stderr)
        
    except Exception as e:
        print(f"#   ⚠️  Error reading configuration: {e}", file=sys.stderr)
    
    print("# ✅ BUILD_FLAGS CMAKE: Ready to generate cmake_flags.cmake", file=sys.stderr)


def main() -> None:
    """Generate CMake variables from build_flags.toml."""
    toml_file = find_toml_file()
    print(f"# Generated from {toml_file} - DO NOT EDIT MANUALLY", file=sys.stderr)
    print(f"# Run build_tools/generate_cmake_flags.py to regenerate", file=sys.stderr)
    
    # Load TOML file using tomli
    try:
        with open(toml_file, 'rb') as f:
            config = tomli.load(f)
    except Exception as e:
        print(f"# ❌ BUILD_FLAGS CMAKE ERROR: Failed to load {toml_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print configuration status
    print_config_status(config, toml_file)
    
    # Extract flags from TOML structure
    all_defines = config.get('all', {}).get('defines', [])
    all_compiler_flags = config.get('all', {}).get('compiler_flags', [])
    library_compiler_flags = config.get('library', {}).get('compiler_flags', [])
    
    # Combine universal + library flags for CMake (matches the original logic)
    combined_flags = all_defines + all_compiler_flags + library_compiler_flags
    
    # Generate CMake variables
    print("# Generated from build_flags.toml - DO NOT EDIT MANUALLY")
    print("# Run build_tools/generate_cmake_flags.py to regenerate")
    print()
    
    # Universal compilation flags (shared by all targets)
    print("set(FASTLED_BASE_COMPILE_FLAGS")
    for flag in combined_flags:
        # Escape any special characters for CMake
        escaped_flag = flag.replace('"', '\\"')
        print(f'    "{escaped_flag}"')
    print(")")
    print()
    
    # Build mode flags
    for mode in ["debug", "quick", "release"]:
        mode_flags = config.get('build_modes', {}).get(mode, {}).get('flags', [])
        
        # For debug mode, add the file prefix map flag from dwarf config
        if mode == "debug":
            dwarf_config = config.get('dwarf', {})
            file_prefix_from = dwarf_config.get('file_prefix_map_from', '/')
            file_prefix_to = dwarf_config.get('file_prefix_map_to', 'sketchsource/')
            file_prefix_flag = f"-ffile-prefix-map={file_prefix_from}={file_prefix_to}"
            mode_flags = mode_flags + [file_prefix_flag]
        
        print(f"set(FASTLED_{mode.upper()}_FLAGS")
        for flag in mode_flags:
            escaped_flag = flag.replace('"', '\\"')
            print(f'    "{escaped_flag}"')
        print(")")
        print()


if __name__ == "__main__":
    main() 