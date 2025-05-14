from pathlib import Path
from typing import List

from fastled_wasm_compiler.insert_header import insert_headers
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.transform_to_cpp import transform_to_cpp

_FILE_EXTENSIONS = [".ino", ".h", ".hpp", ".cpp"]


def process_ino_files(src_dir: Path) -> None:
    transform_to_cpp(src_dir)
    exclusion_folders: List[Path] = []
    insert_headers(src_dir, exclusion_folders, _FILE_EXTENSIONS)

    # print out what is here now in the current directory:
    print(
        f"Current directory: {src_dir} structure has {[dir for dir in src_dir.iterdir()]}"
    )
    print(banner("Transform to cpp and insert header operations completed."))
