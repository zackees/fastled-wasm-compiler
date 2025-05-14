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


import os
import shutil
import sys
import traceback
import warnings
from pathlib import Path
from typing import List

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile import compile

# copy_output_files_and_create_manifest
from fastled_wasm_compiler.copy_files_and_output_manifest import (
    copy_output_files_and_create_manifest,
)
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.process_ino_files import process_ino_files
from fastled_wasm_compiler.types import BuildMode


def copy_files(src_dir: Path, js_src: Path) -> None:
    print("Copying files from mapped directory to container...")
    found = False
    for item in src_dir.iterdir():
        found = True
        if item.is_dir():
            print(f"Copying directory: {item}")
            shutil.copytree(item, js_src / item.name, dirs_exist_ok=True)
        else:
            print(f"Copying file: {item} -> {js_src / item.name}")
            if "platformio.ini" in item.name:
                print(f"Skipping {item} as it is a PlatformIO configuration file.")
                continue
            if "wasm_compiler_flags.py" in item.name:
                print(f"Skipping {item} as it is a compiler flags file.")
                continue
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
    rtn = compile(
        compiler_root=js_dir,
        build_mode=build_mode,
        auto_clean=auto_clean,
        no_platformio=no_platformio,
    )
    print(f"Compilation return code: {rtn}")
    if rtn != 0:
        print("Compilation failed.")
        raise RuntimeError("Compilation failed.")
    print(banner("Compilation successful."))


def _get_build_dir_platformio(build_mode: BuildMode, pio_dir: Path) -> Path:
    # First assert there is only one build artifact directory.
    # The name is dynamic: it's your sketch folder name.
    # build_dirs = [d for d in pio_dir.iterdir() if d.is_dir()]
    # if len(build_dirs) != 1:
    #     raise RuntimeError(
    #         f"Expected exactly one build directory in {pio_dir}, found {len(build_dirs)}: {build_dirs}"
    #     )
    # build_dir: Path = build_dirs[0]
    # return build_dir
    if build_mode == BuildMode.DEBUG:
        build_dir = pio_dir / "wasm-debug"
    elif build_mode == BuildMode.RELEASE:
        build_dir = pio_dir / "wasm-release"
    else:
        build_dir = pio_dir / "wasm-quick"
    if not build_dir.exists():
        raise RuntimeError(
            f"Expected build directory {build_dir} to exist, but it does not."
        )
    sub_dirs = [d for d in build_dir.iterdir() if d.is_dir()]
    if len(sub_dirs) != 1:
        raise RuntimeError(
            f"Expected exactly one subdirectory in {build_dir}, found {len(sub_dirs)}: {sub_dirs}"
        )
    return build_dir


def _get_workspace_from_platformio(platformio_ini_content: str) -> str | None:
    """
    Extract the workspace directory from the PlatformIO configuration file.

    Args:
        platformio_ini_content (str): The content of the PlatformIO configuration file.

    Returns:
        str | None: The workspace directory if found, otherwise None.
    """
    lines = platformio_ini_content.splitlines()
    for line in lines:
        if line.startswith("workspace_dir"):
            return line.split("=")[1].strip()
    return None


def run(args: Args) -> int:
    assets_dir = args.assets_dirs
    assert assets_dir.exists(), f"Assets directory {assets_dir} does not exist."

    index_html = assets_dir / "index.html"
    index_css_src = assets_dir / "index.css"
    index_js_src = assets_dir / "index.js"

    compiler_root = args.compiler_root

    sketch_tmp = compiler_root / "src"
    pio_build_dir = compiler_root / ".pio/build"
    assets_modules = assets_dir / "modules"
    clear_ccache = args.clear_ccache

    # _OUTPUT_FILES = ["fastled.js", "fastled.wasm"]

    # _MAX_COMPILE_ATTEMPTS = 1  # Occasionally the compiler fails for unknown reasons, but disabled because it increases the build time on failure.
    fastled_js_out = "fastled_js"

    check_paths: list[Path] = [
        compiler_root,
        index_html,
        index_css_src,
        index_js_src,
        assets_dir,
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
        # TODO: replace these flags with something better.
        any_only_flags = args.only_copy or args.only_insert_header or args.only_compile
        do_copy = not any_only_flags or args.only_copy
        do_insert_header = not any_only_flags or args.only_insert_header
        do_compile = not any_only_flags or args.only_compile

        if not any_only_flags:
            if sketch_tmp.exists():
                print(f"Normal build, so removing {sketch_tmp}")
                shutil.rmtree(sketch_tmp)

        sketch_tmp.mkdir(parents=True, exist_ok=True)

        if do_copy:
            copy_files(src_dir, sketch_tmp)
            if args.only_copy:
                return 0

        if do_insert_header:
            process_ino_files(sketch_tmp)
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

                if clear_ccache:
                    print("Clearing ccache...")
                    os.system("ccache -C")

                # # Clear out the build directory if it exists
                # if pio_build_dir.iterdir():
                #     print(f"Removing existing build directory: {pio_build_dir}")
                #     for item in pio_build_dir.iterdir():
                #         if item.is_dir():
                #             print(f"Removing directory: {item}")
                #             shutil.rmtree(item)
                #         else:
                #             item.unlink()
                process_compile(
                    js_dir=compiler_root,
                    build_mode=build_mode,
                    auto_clean=not args.disable_auto_clean,
                    no_platformio=no_platformio,
                )
            except Exception as e:
                print(f"Error: {str(e)}")
                return 1

            if no_platformio:
                build_dir = compiler_root / "build"
            else:
                build_dir = _get_build_dir_platformio(
                    build_mode=build_mode, pio_dir=pio_build_dir
                )

            # Copy output files and create manifest
            copy_output_files_and_create_manifest(
                build_dir=build_dir,
                src_dir=src_dir,
                fastled_js_out=fastled_js_out,
                index_html=index_html,
                index_css_src=index_css_src,
                index_js_src=index_js_src,
                assets_modules=assets_modules,
            )
            # # remove the pio_build_dir
            # if pio_build_dir.exists():
            #     shutil.rmtree(pio_build_dir)
        # cleanup(args, sketch_tmp)

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
