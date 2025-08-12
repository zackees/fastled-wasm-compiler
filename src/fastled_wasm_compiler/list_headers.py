"""Module for listing and dumping header files."""

import os
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import EMSDK_PATH


def get_emsdk_headers(output_path: Path) -> int:
    """Get all EMSDK header files and save them to a zip file or directory.

    Args:
        output_path: Path to the output zip file or directory where headers will be saved.
                    If the path ends with .zip, creates a zip file.
                    Otherwise, creates a directory structure.

    Returns:
        Exit code: 0 for success, 1 for error
    """
    import shutil
    import zipfile

    emsdk_path = Path(EMSDK_PATH)

    if not emsdk_path.exists():
        print(f"Error: EMSDK path {EMSDK_PATH} does not exist")
        return 1

    print(f"EMSDK Headers from {EMSDK_PATH}:")
    print(f"Output path: {output_path}")

    # Determine if we're creating a zip file or directory
    is_zip_output = str(output_path).lower().endswith(".zip")
    print(f"Output format: {'ZIP file' if is_zip_output else 'Directory structure'}")
    print("=" * 50)

    header_extensions = {".h", ".hpp", ".hh", ".h++", ".hxx"}
    header_count = 0

    try:
        if is_zip_output:
            # Ensure output directory exists for zip file
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(emsdk_path):
                    for file in files:
                        if any(file.endswith(ext) for ext in header_extensions):
                            header_path = Path(root) / file
                            relative_path = header_path.relative_to(emsdk_path)

                            # Add file to zip archive
                            zipf.write(header_path, f"emsdk_headers/{relative_path}")
                            print(f"  {relative_path}")
                            header_count += 1
        else:
            # Create directory structure
            output_path.mkdir(parents=True, exist_ok=True)
            emsdk_headers_dir = output_path / "emsdk_headers"
            emsdk_headers_dir.mkdir(exist_ok=True)

            for root, dirs, files in os.walk(emsdk_path):
                for file in files:
                    if any(file.endswith(ext) for ext in header_extensions):
                        header_path = Path(root) / file
                        relative_path = header_path.relative_to(emsdk_path)

                        # Create target directory and copy file
                        target_path = emsdk_headers_dir / relative_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(header_path, target_path)
                        print(f"  {relative_path}")
                        header_count += 1

        print("=" * 50)
        print(f"Total EMSDK headers found: {header_count}")
        print(f"Headers saved to: {output_path}")
        return 0

    except Exception as e:
        print(f"Error processing EMSDK headers: {e}")
        return 1


def list_emsdk_headers() -> int:
    """List all EMSDK header files and return exit code.

    This is a legacy function that prints headers to stdout.
    Use get_emsdk_headers() to save headers to a zip file.
    """
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
