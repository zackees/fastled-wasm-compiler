import json
import shutil
from pathlib import Path

from utils import banner, hash_file


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
    assets_dir: Path,
    generate_index_html: bool = False,
) -> None:
    """
    Copy all output files to the destination directory and create manifest.

    Copies Vite-built frontend from assets_dir/dist/ and fastled.* build
    artifacts from build_dir.

    Args:
        build_dir: Path to the build directory containing compiled artifacts
        src_dir: Path to the source directory
        fastled_js_out: Name of the output directory
        assets_dir: Path to the compiler assets directory (containing dist/)
        generate_index_html: Whether to generate an additional platform index.html
    """
    print(banner("Copying output files..."))
    out_dir: Path = src_dir / fastled_js_out
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy all fastled.* build artifacts
    for file_path in build_dir.glob("fastled.*"):
        _dst = out_dir / file_path.name
        print(f"Copying {file_path} to {_dst}")
        shutil.copy2(file_path, _dst)

    # Copy Vite build output from dist/
    dist_dir = assets_dir / "dist"
    if not dist_dir.exists():
        raise RuntimeError(
            f"Vite build output not found at {dist_dir}. "
            + f"Run 'npm install && npx vite build' in {assets_dir}"
        )

    print(f"Copying Vite build output from {dist_dir} to {out_dir}")
    for item in dist_dir.iterdir():
        dest = out_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    optional_input_data_dir = src_dir / "data"
    output_data_dir = out_dir / optional_input_data_dir.name

    # Process data directory and create manifest
    manifest = process_embedded_data_directory(optional_input_data_dir, output_data_dir)

    # Write manifest file even if empty
    print(banner("Writing manifest files.json"))
    manifest_json_str = json.dumps(manifest, indent=2, sort_keys=True)
    with open(out_dir / "files.json", "w") as f:
        f.write(manifest_json_str)

    # Optionally generate a platform-style index.html for artifacts
    if generate_index_html:
        print(banner("Generating platform index.html"))
        try:
            # Import from the same tools directory
            from generate_index import (
                generate_manifest_json,
                generate_platform_index_html,
                get_file_info,
            )

            # Collect all files in the output directory
            wasm_files = []
            for file_path in out_dir.iterdir():
                if file_path.is_file():
                    wasm_files.append(get_file_info(file_path))

            # Create platform info structure
            platforms = {
                "wasm": {
                    "display_name": "WebAssembly Build",
                    "description": "Compiled WebAssembly modules and supporting files",
                    "files": wasm_files,
                }
            }

            # Generate the index.html in the parent directory
            generate_platform_index_html(
                src_dir,
                platforms,
                title="FastLED WASM Compiler - Build Artifacts",
                subtitle="WebAssembly compilation output",
            )

            # Also generate a JSON manifest
            generate_manifest_json(
                src_dir,
                platforms,
                {"build_type": "wasm", "output_directory": fastled_js_out},
            )

        except ImportError:
            print(
                "Warning: Could not import tools/generate_index.py for HTML generation"
            )
        except Exception as e:
            print(f"Warning: Failed to generate platform index.html: {e}")
