import re
from pathlib import Path

from fastled_wasm_compiler.print_banner import banner

_HEADERS_TO_INSERT = ["#include <Arduino.h>"]


def insert_header(file: Path) -> None:
    print(f"Inserting header in file: {file}")
    with open(file, "r") as f:
        content = f.read()

    # Remove existing includes
    for header in _HEADERS_TO_INSERT:
        content = re.sub(
            rf"^.*{re.escape(header)}.*\n", "", content, flags=re.MULTILINE
        )

    # Remove both versions of Arduino.h include
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
    print(banner("Inserting headers in source files..."))
    for file in src_dir.rglob("*"):
        if (
            file.suffix in file_extensions
            and not any(folder in file.parents for folder in exclusion_folders)
            and file.name != "Arduino.h"
        ):
            insert_header(file)
