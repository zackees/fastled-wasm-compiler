# A compilation script specific to fastled's docker compiler.
# This script will pull the users code from a mapped directory,
# then do some processing to convert the *.ino files to *.cpp and
# insert certain headers like "Arduino.h" (pointing to a fake implementation).
# After this, the code is compiled, and the output files are copied back
# to the users mapped directory in the fastled_js folder.
# There are a few assumptions for this script:
# 1. The mapped directory will contain only one directory with the users code, this is
#    enforced by the script that sets up the docker container.
# 2. The docker container has installed compiler dependencies in the /js directory.


import json
import os
import shutil
import sys
import traceback
import warnings
from pathlib import Path
from typing import List

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.cleanup import cleanup
from fastled_wasm_compiler.compile import compile
from fastled_wasm_compiler.hashfile import hash_file
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.process_ino_files import process_ino_files
from fastled_wasm_compiler.types import BuildMode

# from fastled_wasm_server.paths import (
#     COMPILER_ROOT,
#     FASTLED_COMPILER_DIR,
#     PIO_BUILD_DIR,
#     SKETCH_SRC,
# )
# from fastled_wasm_server.print_banner import banner
# from fastled_wasm_server.types import BuildMode


print("Finished imports...")

# TODO: Move these to a config file


# DateLine class removed as it's no longer needed with streaming timestamps


def copy_files(src_dir: Path, js_src: Path) -> None:
    print("Copying files from mapped directory to container...")
    found = False
    for item in src_dir.iterdir():
        found = True
        if item.is_dir():
            print(f"Copying directory: {item}")
            shutil.copytree(item, js_src / item.name, dirs_exist_ok=True)
        else:
            print(f"Copying file: {item}")
            shutil.copy2(item, js_src / item.name)
    if not found:
        warnings.warn(f"No files found in the mapped directory: {src_dir.absolute()}")


def find_project_dir(mapped_dir: Path) -> Path:
    mapped_dirs: List[Path] = list(mapped_dir.iterdir())
    if len(mapped_dirs) > 1:
        raise ValueError(
            f"Error: More than one directory found in {mapped_dir}, which are {mapped_dirs}"
        )

    src_dir: Path = mapped_dirs[0]
    return src_dir


def process_compile(
    js_dir: Path, build_mode: BuildMode, auto_clean: bool, no_platformio: bool
) -> None:
    print("Starting compilation...")
    rtn = compile(js_dir, build_mode, auto_clean, no_platformio=no_platformio)
    print(f"Compilation return code: {rtn}")
    if rtn != 0:
        print("Compilation failed.")
        raise RuntimeError("Compilation failed.")
    print(banner("Compilation successful."))


def _get_build_dir_platformio(pio_dir: Path) -> Path:
    # First assert there is only one build artifact directory.
    # The name is dynamic: it's your sketch folder name.
    build_dirs = [d for d in pio_dir.iterdir() if d.is_dir()]
    if len(build_dirs) != 1:
        raise RuntimeError(
            f"Expected exactly one build directory in {pio_dir}, found {len(build_dirs)}: {build_dirs}"
        )
    build_dir: Path = build_dirs[0]
    return build_dir


def run(args: Args) -> int:
    _INDEX_HTML_SRC = args.index_html
    COMPILER_ROOT = args.compiler_root

    FASTLED_COMPILER_DIR = COMPILER_ROOT / "fastled/src/platforms/wasm/compiler"
    SKETCH_SRC = COMPILER_ROOT / "src"
    PIO_BUILD_DIR = COMPILER_ROOT / ".pio/build"

    _FASTLED_MODULES_DIR = FASTLED_COMPILER_DIR / "modules"
    _INDEX_CSS_SRC = args.style_css
    _INDEX_JS_SRC = args.index_js

    _WASM_COMPILER_SETTTINGS = args.compiler_flags
    # _OUTPUT_FILES = ["fastled.js", "fastled.wasm"]

    # _MAX_COMPILE_ATTEMPTS = 1  # Occasionally the compiler fails for unknown reasons, but disabled because it increases the build time on failure.
    _FASTLED_OUTPUT_DIR_NAME = "fastled_js"

    check_paths: list[Path] = [
        COMPILER_ROOT,
        _INDEX_HTML_SRC,
        _INDEX_CSS_SRC,
        _INDEX_JS_SRC,
        _WASM_COMPILER_SETTTINGS,
        FASTLED_COMPILER_DIR,
    ]
    missing_paths = [p for p in check_paths if not p.exists()]
    if missing_paths:
        print("The following paths are missing:")
        for p in missing_paths:
            print(p)
        missing_paths_str = ",".join(str(p.as_posix()) for p in missing_paths)
        raise FileNotFoundError(f"Missing required paths: {missing_paths_str}")

    print("Starting FastLED WASM compilation script...")
    print(f"Keep files flag: {args.keep_files}")
    print(f"Using mapped directory: {args.mapped_dir}")

    if args.profile:
        print(banner("Enabling profiling for compilation."))
        # Profile linking
        os.environ["EMPROFILE"] = "2"
    else:
        print(
            banner(
                "Build process profiling is disabled\nuse --profile to get metrics on how long the build process took."
            )
        )

    try:

        src_dir = find_project_dir(args.mapped_dir)

        any_only_flags = args.only_copy or args.only_insert_header or args.only_compile

        do_copy = not any_only_flags or args.only_copy
        do_insert_header = not any_only_flags or args.only_insert_header
        do_compile = not any_only_flags or args.only_compile

        if not any_only_flags:
            if SKETCH_SRC.exists():
                shutil.rmtree(SKETCH_SRC)

        SKETCH_SRC.mkdir(parents=True, exist_ok=True)

        if do_copy:
            copy_files(src_dir, SKETCH_SRC)
            if args.only_copy:
                return 0

        if do_insert_header:
            process_ino_files(SKETCH_SRC)
            if args.only_insert_header:
                print("Transform to cpp and insert header operations completed.")
                return 0

        no_platformio: bool = args.no_platformio

        if do_compile:
            try:
                # Determine build mode from args
                if args.debug:
                    build_mode = BuildMode.DEBUG
                elif args.release:
                    build_mode = BuildMode.RELEASE
                else:
                    # Default to QUICK mode if neither debug nor release specified
                    build_mode = BuildMode.QUICK

                process_compile(
                    js_dir=COMPILER_ROOT,
                    build_mode=build_mode,
                    auto_clean=not args.disable_auto_clean,
                    no_platformio=no_platformio,
                )
            except Exception as e:
                print(f"Error: {str(e)}")
                return 1

            def _get_build_dir_cmake() -> Path:
                return COMPILER_ROOT / "build"

            if no_platformio:
                build_dir = _get_build_dir_cmake()
            else:
                build_dir = _get_build_dir_platformio(PIO_BUILD_DIR)

            print(banner("Copying output files..."))
            out_dir: Path = src_dir / _FASTLED_OUTPUT_DIR_NAME
            out_dir.mkdir(parents=True, exist_ok=True)

            # Copy all fastled.* build artifacts
            for file_path in build_dir.glob("fastled.*"):
                _dst = out_dir / file_path.name
                print(f"Copying {file_path} to {_dst}")
                shutil.copy2(file_path, _dst)

            # Copy static files.
            print(f"Copying {_INDEX_HTML_SRC} to output directory")
            shutil.copy2(_INDEX_HTML_SRC, out_dir / "index.html")
            print(f"Copying {_INDEX_CSS_SRC} to output directory")
            shutil.copy2(_INDEX_CSS_SRC, out_dir / "index.css")

            # copy all js files in _FASTLED_COMPILER_DIR to output directory
            Path(out_dir / "modules").mkdir(parents=True, exist_ok=True)

            # Recursively copy all non-hidden files and directories
            print(f"Copying files from {_FASTLED_MODULES_DIR} to {out_dir / 'modules'}")
            shutil.copytree(
                src=_FASTLED_MODULES_DIR,
                dst=out_dir / "modules",
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".*"),
            )  # Ignore hidden files

            print("Copying index.js to output directory")
            shutil.copy2(_INDEX_JS_SRC, out_dir / "index.js")
            optional_input_data_dir = src_dir / "data"
            output_data_dir = out_dir / optional_input_data_dir.name

            # Handle data directory if it exists
            manifest: list[dict] = []
            if optional_input_data_dir.exists():
                # Clean up existing output data directory
                if output_data_dir.exists():
                    for _file in output_data_dir.iterdir():
                        _file.unlink()

                # Create output data directory and copy files
                output_data_dir.mkdir(parents=True, exist_ok=True)
                for _file in optional_input_data_dir.iterdir():
                    if _file.is_file():  # Only copy files, not directories
                        filename: str = _file.name
                        if filename.endswith(".embedded.json"):
                            print(banner("Embedding data file"))
                            filename_no_embedded = filename.replace(
                                ".embedded.json", ""
                            )
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

            # Write manifest file even if empty
            print(banner("Writing manifest files.json"))
            manifest_json_str = json.dumps(manifest, indent=2, sort_keys=True)
            with open(out_dir / "files.json", "w") as f:
                f.write(manifest_json_str)
        cleanup(args, SKETCH_SRC)

        print(banner("Compilation process completed successfully"))
        return 0

    except Exception as e:

        stacktrace = traceback.format_exc()
        print(stacktrace)
        print(f"Error: {str(e)}")
        return 1


def main() -> int:
    args = Args.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
