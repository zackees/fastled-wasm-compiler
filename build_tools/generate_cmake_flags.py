#!/usr/bin/env python3
"""
Generate CMake variables from centralized compilation_flags.toml.
This ensures CMakeLists.txt uses the same flags as sketch compilation.
"""

import sys
from pathlib import Path

# Require tomli - fail if not available
try:
    import tomli
except ImportError:
    print("FATAL ERROR: tomli module is required but not installed.", file=sys.stderr)
    print("Install it with: pip3 install tomli", file=sys.stderr)
    print("This is a controlled environment - dependencies must be explicit.", file=sys.stderr)
    sys.exit(1)


def find_toml_file() -> Path:
    """Find the compilation_flags.toml file."""
    # Try multiple possible locations
    possible_paths = [
        # Docker container paths
        Path("/tmp/fastled-wasm-compiler-install/src/fastled_wasm_compiler/compilation_flags.toml"),
        # Local development paths
        Path(__file__).parent.parent / "src" / "fastled_wasm_compiler" / "compilation_flags.toml",
        # Relative paths
        Path("src/fastled_wasm_compiler/compilation_flags.toml"),
        Path("../src/fastled_wasm_compiler/compilation_flags.toml"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    print(f"ERROR: Could not find compilation_flags.toml in any of these locations:", file=sys.stderr)
    for path in possible_paths:
        print(f"  - {path}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """Generate CMake variables from compilation_flags.toml."""
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
    print("# Generated from compilation_flags.toml - DO NOT EDIT MANUALLY")
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