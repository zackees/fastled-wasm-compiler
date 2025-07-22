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
    return os.environ.get("ENV_FASTLED_SOURCE_PATH", "git/fastled/src")


def find_toml_file() -> Path:
    """Find the build_flags.toml file with fallback logic."""
    # Try FastLED source tree first
    try:
        fastled_src_path = Path(get_fastled_source_path())
        fastled_build_flags = fastled_src_path / "platforms" / "wasm" / "compile" / "build_flags.toml"
        
        if fastled_build_flags.exists():
            print(f"# Using build flags from FastLED source: {fastled_build_flags}", file=sys.stderr)
            return fastled_build_flags
    except Exception as e:
        print(f"# Could not check FastLED source tree: {e}", file=sys.stderr)
    
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
    
    for path in possible_paths:
        if path.exists():
            print(f"# Using fallback build flags: {path}", file=sys.stderr)
            return path
    
    print(f"ERROR: Could not find build_flags.toml in any of these locations:", file=sys.stderr)
    for path in possible_paths:
        print(f"  - {path}", file=sys.stderr)
    sys.exit(1)


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
        print(f"ERROR: Failed to load {toml_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract flags from TOML structure
    base_defines = config.get('base', {}).get('defines', [])
    base_compiler_flags = config.get('base', {}).get('compiler_flags', [])
    library_compiler_flags = config.get('library', {}).get('compiler_flags', [])
    
    # Combine base + library flags for CMake (matches the original logic)
    all_flags = base_defines + base_compiler_flags + library_compiler_flags
    
    # Generate CMake variables
    print("# Generated from build_flags.toml - DO NOT EDIT MANUALLY")
    print("# Run build_tools/generate_cmake_flags.py to regenerate")
    print()
    
    # Base compilation flags
    print("set(FASTLED_BASE_COMPILE_FLAGS")
    for flag in all_flags:
        # Escape any special characters for CMake
        escaped_flag = flag.replace('"', '\\"')
        print(f'    "{escaped_flag}"')
    print(")")
    print()
    
    # Build mode flags
    for mode in ["debug", "quick", "release"]:
        mode_flags = config.get('build_modes', {}).get(mode, {}).get('flags', [])
        print(f"set(FASTLED_{mode.upper()}_FLAGS")
        for flag in mode_flags:
            escaped_flag = flag.replace('"', '\\"')
            print(f'    "{escaped_flag}"')
        print(")")
        print()


if __name__ == "__main__":
    main() 