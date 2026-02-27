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


import shutil
import sys
import traceback
import warnings
from pathlib import Path

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile import compile

# copy_output_files_and_create_manifest
from fastled_wasm_compiler.copy_files_and_output_manifest import (
    copy_output_files_and_create_manifest,
)
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.process_ino_files import process_ino_files
from fastled_wasm_compiler.types import BuildMode
from fastled_wasm_compiler.vite_build import ensure_vite_built


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
            shutil.copy2(item, js_src / item.name)
    if not found:
        warnings.warn(f"No files found in the mapped directory: {src_dir.absolute()}")


def find_project_dir(mapped_dir: Path) -> Path:
    """Find the sketch directory within the mapped directory.

    The mapped directory may contain multiple subdirectories including 'sketch' and 'headers_output'.
    This function specifically looks for and returns the 'sketch' directory.
    """
    sketch_dir = mapped_dir / "sketch"
    if sketch_dir.exists() and sketch_dir.is_dir():
        return sketch_dir

    # Fallback: if no 'sketch' directory found, check if there's only one directory
    # (for backward compatibility with older test data structures)
    mapped_dirs: list[Path] = [d for d in mapped_dir.iterdir() if d.is_dir()]
    if len(mapped_dirs) == 1:
        return mapped_dirs[0]

    raise ValueError(
        f"Error: Could not find 'sketch' directory in {mapped_dir}. "
        + f"Available directories: {mapped_dirs}"
    )


def process_compile(
    js_dir: Path,
    build_mode: BuildMode,
    auto_clean: bool,
    profile_build: bool,
) -> None:
    print("Starting compilation...")
    rtn = compile(
        compiler_root=js_dir,
        build_mode=build_mode,
        auto_clean=auto_clean,
        profile_build=profile_build,
    )
    print(f"Compilation return code: {rtn}")
    if rtn != 0:
        print("Compilation failed.")
        raise RuntimeError("Compilation failed.")
    print(banner("Compilation successful."))


def run_compile(args: Args) -> int:
    assets_dir = args.assets_dirs

    assert assets_dir.exists(), f"Assets directory {assets_dir} does not exist."

    # Determine directories based on session_id
    if args.session_id is not None:
        # Use session-based persistent directories
        from fastled_wasm_compiler.session_directory_manager import (
            get_session_directory_manager,
        )

        session_mgr = get_session_directory_manager()
        session_mgr.ensure_session_structure(args.session_id)

        # Override compiler_root to use session directory
        compiler_root = session_mgr.get_session_dir(args.session_id)
        sketch_tmp = session_mgr.get_session_src_dir(args.session_id)
        print(f"Using session-based directory: {compiler_root}")
        print(f"  Session ID: {args.session_id}")
        print(f"  Sketch source: {sketch_tmp}")
    else:
        # Use traditional temporary directories
        compiler_root = args.compiler_root
        sketch_tmp = compiler_root / "src"
        print(f"Using traditional compiler root: {compiler_root}")

    pio_build_dir = compiler_root / ".pio/build"

    fastled_js_out = "fastled_js"

    check_paths: list[Path] = [
        compiler_root,
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

    try:

        src_dir = find_project_dir(args.mapped_dir)
        # TODO: replace these flags with something better.
        any_only_flags = args.only_copy or args.only_insert_header or args.only_compile
        do_copy = not any_only_flags or args.only_copy
        do_insert_header = not any_only_flags or args.only_insert_header
        do_compile = not any_only_flags or args.only_compile

        # Always clean sketch_tmp before copying to ensure fresh files
        # This prevents stale cached files from being compiled
        if sketch_tmp.exists() and (do_copy or not any_only_flags):
            print(f"Cleaning sketch directory to ensure fresh files: {sketch_tmp}")
            shutil.rmtree(sketch_tmp)

        sketch_tmp.mkdir(parents=True, exist_ok=True)

        # Always copy fresh files when compiling (unless --only-insert-header without copy)
        # This ensures the compiler never uses stale cached source files
        if do_copy or do_compile:
            copy_files(src_dir, sketch_tmp)
            if args.only_copy:
                return 0

        # Always run header insertion when compiling to ensure .ino files are transformed
        # This prevents stale .ino.cpp files from being used
        if do_insert_header or do_compile:
            process_ino_files(sketch_tmp)
            if args.only_insert_header:
                print("Transform to cpp and insert header operations completed.")
                return 0

        if do_compile:
            try:
                # Determine build mode from args
                if args.debug:
                    build_mode = BuildMode.DEBUG
                elif args.fast_debug:
                    build_mode = BuildMode.FAST_DEBUG
                elif args.release:
                    build_mode = BuildMode.RELEASE
                else:
                    # Default to QUICK mode if neither debug nor release specified
                    build_mode = BuildMode.QUICK

                print(
                    banner(
                        f"Starting compilation process with mode: {build_mode}\n  js_dir: {compiler_root}\n  profile_build: {args.profile}"
                    )
                )
                process_compile(
                    js_dir=compiler_root,
                    build_mode=build_mode,
                    auto_clean=not args.disable_auto_clean,
                    profile_build=args.profile,
                )
            except Exception as e:
                print(f"Error: {str(e)}")
                return 1

            # The compile_sketch.py creates subdirectories based on build mode
            if args.session_id is not None:
                # Use session-specific build directory
                from fastled_wasm_compiler.session_directory_manager import (
                    get_session_directory_manager,
                )

                session_mgr = get_session_directory_manager()
                build_dir = session_mgr.get_session_build_dir(
                    args.session_id, build_mode.name.lower()
                )
            else:
                # Use global build directory
                from fastled_wasm_compiler.paths import BUILD_ROOT

                build_dir = BUILD_ROOT / build_mode.name.lower()
            print(banner("Build directory structure"))
            print(f"✓ Using direct compilation build directory: {build_dir}")
            print(f"✓ Build mode subdirectory: {build_mode.name.lower()}")
            print("✓ Expected output files: fastled.js, fastled.wasm")
            if not build_dir.exists():
                print(
                    f"⚠️  Build directory {build_dir} does not exist yet (will be created during compilation)"
                )
            else:
                print(f"✓ Build directory exists: {build_dir}")

            # Ensure Vite frontend is built (builds if dist/ is missing)
            ensure_vite_built(assets_dir)

            # Copy output files and create manifest
            copy_output_files_and_create_manifest(
                build_dir=build_dir,
                src_dir=src_dir,
                fastled_js_out=fastled_js_out,
                assets_dir=assets_dir,
            )

            # Add build summary
            print(banner("Build Summary"))
            print("✅ Compilation method: Direct emcc calls")
            print(f"✅ Build mode: {build_mode.name}")
            print(f"✅ Build directory: {build_dir}")
            print(f"✅ Source directory: {src_dir}")
            print(f"✅ Output directory: {fastled_js_out}")

            # Check for expected output files
            expected_files = ["fastled.js", "fastled.wasm"]
            if build_mode == BuildMode.DEBUG:
                expected_files.append("fastled.wasm.dwarf")

            print(f"📁 Checking output files in {src_dir / fastled_js_out}:")
            output_dir = src_dir / fastled_js_out
            for file_name in expected_files:
                file_path = output_dir / file_name
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  ✅ {file_name} ({size} bytes)")
                else:
                    print(f"  ❌ {file_name} (missing)")

            print("🎯 Build completed using direct emscripten compilation")

            # remove the pio_build_dir and sketch build directory.
            if not args.keep_files:
                print(
                    banner(
                        f"Cleaning up directories:\n  build ({pio_build_dir}) and\n  sketch ({sketch_tmp})"
                    )
                )
                if pio_build_dir.exists() and not args.keep_files:
                    shutil.rmtree(pio_build_dir, ignore_errors=True)
                if sketch_tmp.exists():
                    shutil.rmtree(sketch_tmp, ignore_errors=True)
                    sketch_tmp.mkdir(parents=True, exist_ok=True)

        print(banner("Compilation process completed successfully"))
        return 0

    except Exception as e:

        stacktrace = traceback.format_exc()
        print(stacktrace)
        print(f"Error: {str(e)}")
        return 1


def main() -> int:
    args = Args.parse_args()
    return run_compile(args)


if __name__ == "__main__":
    sys.exit(main())
