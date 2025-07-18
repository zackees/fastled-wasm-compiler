"""
CLI for lazy FastLED library building.

This provides a command-line interface for the lazy rebuild functionality.
"""

import sys

from fastled_wasm_compiler.build_lib_lazy import main as build_lib_lazy_main


def main() -> int:
    """Main entry point for the lazy library build CLI."""
    return build_lib_lazy_main()


if __name__ == "__main__":
    sys.exit(main())
