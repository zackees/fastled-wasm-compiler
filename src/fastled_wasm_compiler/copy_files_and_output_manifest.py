import json
import shutil
from pathlib import Path

from fastled_wasm_compiler.hashfile import hash_file
from fastled_wasm_compiler.print_banner import banner


def process_embedded_data_directory(
    input_data_dir: Path, output_data_dir: Path
) -> list[dict]:
    """
    Process the optional data directory, copying files and creating manifest entries.

    Args:
        input_data_dir: Path to the input data directory
        output_data_dir: Path to the output data directory

    Returns:
        List of manifest entries for the data files
    """
    manifest: list[dict] = []

    if input_data_dir.exists():
        # Clean up existing output data directory
        if output_data_dir.exists():
            for _file in output_data_dir.iterdir():
                _file.unlink()

        # Create output data directory and copy files
        output_data_dir.mkdir(parents=True, exist_ok=True)
        for _file in input_data_dir.iterdir():
            if _file.is_file():  # Only copy files, not directories
                filename: str = _file.name
                if filename.endswith(".embedded.json"):
                    print(banner("Embedding data file"))
                    filename_no_embedded = filename.replace(".embedded.json", "")
                    # read json file
                    with open(_file, "r") as f:
                        data = json.load(f)
                    hash_value = data["hash"]
                    size = data["size"]
                    manifest.append(
                        {
                            "name": filename_no_embedded,
                            "path": f"data/{filename_no_embedded}",
                            "size": size,
                            "hash": hash_value,
                        }
                    )
                else:
                    print(f"Copying {_file.name} -> {output_data_dir}")
                    shutil.copy2(_file, output_data_dir / _file.name)
                    hash = hash_file(_file)
                    manifest.append(
                        {
                            "name": _file.name,
                            "path": f"data/{_file.name}",
                            "size": _file.stat().st_size,
                            "hash": hash,
                        }
                    )

    return manifest


def find_all_files_from_root_js() -> list[Path]:
    """
    Find all files in the root directory of the js folder.
    """
    root_dir = Path("/")
    return list(root_dir.glob("**/*"))


def copy_output_files_and_create_manifest(
    build_dir: Path,
    src_dir: Path,
    fastled_js_out: str,
    index_html: Path,
    index_css_src: Path,
    index_js_src: Path,
    assets_modules: Path,
) -> None:
    """
    Copy all output files to the destination directory and create manifest.

    Args:
        build_dir: Path to the build directory containing compiled artifacts
        src_dir: Path to the source directory
        fastled_js_out: Name of the output directory
        index_html: Path to the index.html file
        index_css_src: Path to the index.css file
        index_js_src: Path to the index.js file
        assets_modules: Path to the modules directory
    """
    print(banner("Copying output files..."))
    out_dir: Path = src_dir / fastled_js_out
    out_dir.mkdir(parents=True, exist_ok=True)

    artifact_files = list(
        build_dir.glob("fastled.*")
    )  # Get all .wasm files in the build directory

    # Copy all fastled.* build artifacts
    for file_path in artifact_files:
        _dst = out_dir / file_path.name
        print(f"Copying {file_path} to {_dst}")
        shutil.copy2(file_path, _dst)

    # must exist fastled.wasm file
    must_exist = "fastled.wasm"
    for file_path in artifact_files:
        if file_path.name == must_exist:
            break
    else:

        print(banner("ERROR! COULD NOT FIND fastled.wasm!!!"))
        # print("Printing out all files")
        # print("in the root directory /")
        # for file_path in find_all_files_from_root_js():
        #     print(f"  {file_path}")

        raise FileNotFoundError(
            f"fastled.wasm not found in {build_dir} after compilation"
        )

    # Copy static files.
    print(f"Copying {index_html} to output directory")
    shutil.copy2(index_html, out_dir / "index.html")
    print(f"Copying {index_css_src} to output directory")
    shutil.copy2(index_css_src, out_dir / "index.css")

    # copy all js files in _FASTLED_COMPILER_DIR to output directory
    Path(out_dir / "modules").mkdir(parents=True, exist_ok=True)

    # Recursively copy all non-hidden files and directories
    print(f"Copying files from {assets_modules} to {out_dir / 'modules'}")
    shutil.copytree(
        src=assets_modules,
        dst=out_dir / "modules",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".*"),
    )  # Ignore hidden files

    print("Copying index.js to output directory")
    shutil.copy2(index_js_src, out_dir / "index.js")
    optional_input_data_dir = src_dir / "data"
    output_data_dir = out_dir / optional_input_data_dir.name

    # Process data directory and create manifest
    manifest = process_embedded_data_directory(optional_input_data_dir, output_data_dir)

    # Write manifest file even if empty
    print(banner("Writing manifest files.json"))
    manifest_json_str = json.dumps(manifest, indent=2, sort_keys=True)
    with open(out_dir / "files.json", "w") as f:
        f.write(manifest_json_str)
