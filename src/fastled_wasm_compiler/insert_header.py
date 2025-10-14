import re
from pathlib import Path

from fastled_wasm_compiler.print_banner import banner

_HEADERS_TO_INSERT = ["#include <Arduino.h>"]


def insert_header(file: Path, is_main_sketch_file: bool = False) -> None:
    """Insert Arduino.h header into a source file.

    Args:
        file: Path to the source file
        is_main_sketch_file: True if this is the main .ino.cpp file, False for auxiliary files
    """
    # For auxiliary .cpp/.h files (not the main sketch), we rely on PCH to provide Arduino.h
    # This avoids redundant includes and lets PCH work transparently
    if not is_main_sketch_file and file.suffix in [".cpp", ".h", ".hpp"]:
        print(f"Skipping Arduino.h injection for auxiliary file (will use PCH): {file}")
        return

    print(f"Inserting header in file: {file}")
    with open(file, "r") as f:
        content = f.read()

    # Remove existing includes
    for header in _HEADERS_TO_INSERT:
        content = re.sub(
            rf"^.*{re.escape(header)}.*\n", "", content, flags=re.MULTILINE
        )

    # Remove both versions of Arduino.h include (quoted and angle brackets)
    # Both forms now resolve to the same file due to consistent include path configuration
    arduino_pattern = r'^\s*#\s*include\s*[<"]Arduino\.h[>"]\s*.*\n'
    content = re.sub(arduino_pattern, "", content, flags=re.MULTILINE)

    # Add new headers at the beginning
    content = "\n".join(_HEADERS_TO_INSERT) + "\n" + content

    with open(file, "w") as f:
        f.write(content)
    print(f"Processed: {file}")


def insert_headers(
    src_dir: Path, exclusion_folders: list[Path], file_extensions: list[str]
) -> None:
    """Insert headers into source files in the sketch directory.

    Args:
        src_dir: Root directory of the sketch
        exclusion_folders: List of folders to exclude from processing
        file_extensions: List of file extensions to process
    """
    print(banner("Inserting headers in source files..."))
    for file in src_dir.rglob("*"):
        if (
            file.suffix in file_extensions
            and not any(folder in file.parents for folder in exclusion_folders)
            and file.name != "Arduino.h"
        ):
            # Check if this is the main .ino.cpp file (directly in src_dir root)
            is_main_file = (
                file.parent == src_dir and file.suffix == ".cpp" and ".ino" in file.name
            )
            insert_header(file, is_main_sketch_file=is_main_file)
