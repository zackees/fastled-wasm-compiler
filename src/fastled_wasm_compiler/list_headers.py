"""Module for listing and dumping header files."""

import os
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import EMSDK_PATH


def list_emsdk_headers() -> int:
    """List all EMSDK header files and return exit code."""
    emsdk_path = Path(EMSDK_PATH)

    if not emsdk_path.exists():
        print(f"Error: EMSDK path {EMSDK_PATH} does not exist")
        return 1

    print(f"EMSDK Headers from {EMSDK_PATH}:")
    print("=" * 50)

    header_extensions = {".h", ".hpp", ".hh", ".h++", ".hxx"}
    header_count = 0

    try:
        for root, dirs, files in os.walk(emsdk_path):
            for file in files:
                if any(file.endswith(ext) for ext in header_extensions):
                    header_path = Path(root) / file
                    relative_path = header_path.relative_to(emsdk_path)
                    print(f"  {relative_path}")
                    header_count += 1

        print("=" * 50)
        print(f"Total EMSDK headers found: {header_count}")
        return 0

    except Exception as e:
        print(f"Error listing EMSDK headers: {e}")
        return 1
