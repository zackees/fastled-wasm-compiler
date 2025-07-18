#!/usr/bin/env python3
"""
Generate CMake variables from centralized compilation_flags.toml.
This ensures CMakeLists.txt uses the same flags as sketch compilation.
"""

import sys
from pathlib import Path

# Add the src directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastled_wasm_compiler.compilation_flags import get_compilation_flags


def main() -> None:
    """Generate CMake variables from compilation_flags.toml."""
    flags_loader = get_compilation_flags()
    
    # Get base flags (shared by all compilation)
    base_flags = flags_loader.get_base_flags()
    
    # Get library-specific flags  
    library_flags = flags_loader.get_library_flags()
    
    # Combine base + library flags for CMake
    all_flags = base_flags + library_flags
    
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
        mode_flags = flags_loader.get_build_mode_flags(mode)
        print(f"set(FASTLED_{mode.upper()}_FLAGS")
        for flag in mode_flags:
            escaped_flag = flag.replace('"', '\\"')
            print(f'    "{escaped_flag}"')
        print(")")
        print()


if __name__ == "__main__":
    main() 