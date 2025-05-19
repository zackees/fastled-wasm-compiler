import argparse
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, auto
from pathlib import Path
from queue import Queue

from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR = FASTLED_SRC.as_posix()

CXX = "/build_tools/ccache-emcxx.sh"
C_CC = "/build_tools/ccache-emcc.sh"

AR = "emar"

# Define which directories to include when compiling
_INCLUSION_DIRS = ["platforms/wasm", "platforms/stub"]

# Base configuration flags common to all build modes
BASE_C_FLAGS = [
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
    "-DFASTLED_FORCE_NAMESPACE=1",
    "-DFASTLED_USE_PROGMEM=0",
    "-DUSE_OFFSET_CONVERTER=0",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    f"-I{FASTLED_SRC_STR}",
]

BASE_CXX_FLAGS = [
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
    "-DFASTLED_FORCE_NAMESPACE=1",
    "-DFASTLED_USE_PROGMEM=0",
    "-DUSE_OFFSET_CONVERTER=0",
    "-std=gnu++17",
    "-fpermissive",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    "-Werror=cast-function-type",
    f"-I{FASTLED_SRC_STR}",
    # We don't do program linking so these don't matter.
    # "-sEXIT_RUNTIME=0",
    # "-sFILESYSTEM=0",
    # "-sUSE_PTHREADS=0",
]

# Debug-specific flags
DEBUG_C_FLAGS = [
    "-g3",
    "-gsource-map",
    "-ffile-prefix-map=/=fastledsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-fno-strict-aliasing",
    "-fno-inline-functions",
    "-fno-unroll-loops",
    "-fno-vectorize",
    "-O0",
]

DEBUG_CXX_FLAGS = [
    "-g3",
    "-gsource-map",
    "-ffile-prefix-map=/=fastledsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-fno-strict-aliasing",
    "-fno-inline-functions",
    "-fno-unroll-loops",
    "-fno-vectorize",
    "-O0",
]

# Quick build flags (light optimization)
QUICK_C_FLAGS = [
    "-O1",
    "-fno-strict-aliasing",
    "-fno-inline-functions",
    "-fno-unroll-loops",
    "-fno-vectorize",
]

QUICK_CXX_FLAGS = [
    "-O1",
    "-fno-strict-aliasing",
    "-fno-inline-functions",
    "-fno-unroll-loops",
    "-fno-vectorize",
]

# Release/optimized build flags
RELEASE_C_FLAGS = [
    "-Oz",  # Aggressive size optimization
]

RELEASE_CXX_FLAGS = [
    "-Oz",  # Aggressive size optimization
]


class BuildMode(Enum):
    DEBUG = auto()
    QUICK = auto()
    RELEASE = auto()

    @classmethod
    def from_string(cls, mode_str: str) -> "BuildMode":
        mode_str = mode_str.upper()
        if mode_str == "DEBUG":
            return cls.DEBUG
        elif mode_str == "QUICK":
            return cls.QUICK
        elif mode_str == "RELEASE":
            return cls.RELEASE
        else:
            raise ValueError(f"Unknown build mode: {mode_str}")


# _PRINT_LOCK = Lock()
_PRINT_QUEUE = Queue()


def _print_worker():
    while True:
        msg = _PRINT_QUEUE.get()
        if msg is None:
            break
        print(msg)
        _PRINT_QUEUE.task_done()


_THREADED_PRINT = threading.Thread(
    target=_print_worker, daemon=True, name="PrintWorker"
)
_THREADED_PRINT.start()


def _locked_print(s: str) -> None:
    """Thread-safe print function."""
    _PRINT_QUEUE.put(s)
    # with _PRINT_LOCK:
    #     print(s)


def get_c_flags(build_mode: BuildMode) -> list[str]:
    """Get the appropriate C flags for the specified build mode."""
    flags = BASE_C_FLAGS.copy()

    if build_mode == BuildMode.DEBUG:
        flags.extend(DEBUG_C_FLAGS)
    elif build_mode == BuildMode.QUICK:
        flags.extend(QUICK_C_FLAGS)
    elif build_mode == BuildMode.RELEASE:
        flags.extend(RELEASE_C_FLAGS)

    return flags


def get_cxx_flags(build_mode: BuildMode) -> list[str]:
    """Get the appropriate CXX flags for the specified build mode."""
    flags = BASE_CXX_FLAGS.copy()

    if build_mode == BuildMode.DEBUG:
        flags.extend(DEBUG_CXX_FLAGS)
    elif build_mode == BuildMode.QUICK:
        flags.extend(QUICK_CXX_FLAGS)
    elif build_mode == BuildMode.RELEASE:
        flags.extend(RELEASE_CXX_FLAGS)

    return flags


def create_safe_obj_name(src_file: Path, src_dir: Path) -> str:
    """
    Create a safe object file name by replacing directory separators with underscores.
    This prevents file name collisions when files from different directories have the same name.
    """
    rel_path = src_file.relative_to(src_dir)
    safe_name = str(rel_path).replace("/", "_").replace("\\", "_")
    return safe_name + ".o"


def compile_c_to_obj(
    src_file: Path,
    src_dir: Path,
    out_dir: Path,
    include_flags: list[str],
    build_mode: BuildMode,
) -> Path:
    """Compile a C source file to an object file."""
    obj_file = out_dir / create_safe_obj_name(src_file, src_dir)
    os.makedirs(out_dir, exist_ok=True)
    c_flags = get_c_flags(build_mode)
    cmd = [C_CC, "-o", str(obj_file), "-c", *c_flags, *include_flags, str(src_file)]
    cmd_str = subprocess.list2cmdline(cmd)
    _locked_print(f"Compiling C: {obj_file}:\n{cmd_str}")
    cp: subprocess.CompletedProcess = subprocess.run(
        cmd, check=False, capture_output=True
    )
    if cp.returncode != 0:
        _locked_print(
            f"❌ Compilation failed for {src_file}: {cp.stderr.decode(errors='replace')}"
        )
        raise subprocess.CalledProcessError(
            returncode=cp.returncode, cmd=cmd, output=cp.stdout, stderr=cp.stderr
        )
    else:
        _locked_print(f"✅ Compiled: {obj_file}:\n{cp.stdout.decode(errors='replace')}")
    return obj_file


def compile_cpp_to_obj(
    src_file: Path,
    src_dir: Path,
    out_dir: Path,
    include_flags: list[str],
    build_mode: BuildMode,
) -> Path:
    """Compile a C++ source file to an object file."""
    obj_file = out_dir / create_safe_obj_name(src_file, src_dir)
    os.makedirs(out_dir, exist_ok=True)
    cxx_flags = get_cxx_flags(build_mode)
    cmd = [CXX, "-o", str(obj_file), "-c", *cxx_flags, *include_flags, str(src_file)]
    cmd_str = subprocess.list2cmdline(cmd)
    _locked_print(f"Compiling C++: {obj_file}:\n{cmd_str}")
    cp: subprocess.CompletedProcess = subprocess.run(
        cmd, check=False, capture_output=True
    )
    if cp.returncode != 0:
        _locked_print(
            f"❌ Compilation failed for {src_file}: {cp.stderr.decode(errors='replace')}"
        )
        raise subprocess.CalledProcessError(
            returncode=cp.returncode, cmd=cmd, output=cp.stdout, stderr=cp.stderr
        )
    else:
        _locked_print(f"✅ Compiled: {obj_file}:\n{cp.stdout.decode(errors='replace')}")
    return obj_file


def compile_source_to_obj(
    src_file: Path,
    src_dir: Path,
    out_dir: Path,
    include_flags: list[str],
    build_mode: BuildMode,
) -> Path:
    """Compile a source file to an object file based on its extension."""
    suffix = src_file.suffix.lower()
    if suffix == ".c":
        return compile_c_to_obj(src_file, src_dir, out_dir, include_flags, build_mode)
    else:  # .cpp, .ino, etc.
        return compile_cpp_to_obj(src_file, src_dir, out_dir, include_flags, build_mode)


def _get_cpu_count() -> int:
    """
    Get the number of CPU cores available on the system.
    Returns:
        int: Number of CPU cores.
    """
    try:
        return os.cpu_count() or 1
    except NotImplementedError:
        return 1


def filter_sources(src_dir: Path) -> list[Path]:
    """
    Filter source files based on inclusion directories.
    Only include files from the root directory and specified inclusion directories.
    """
    sources = []

    for ext in ["*.c", "*.cpp", "*.ino"]:
        for file_path in src_dir.rglob(ext):
            rel_path = file_path.relative_to(src_dir)
            rel_path_str = str(rel_path)

            # Check if we're in a platforms subdirectory
            parts = rel_path.parts
            in_platforms = len(parts) >= 1 and parts[0] == "platforms"

            # Check if we're in an inclusion directory
            in_inclusion = any(incl in rel_path_str for incl in _INCLUSION_DIRS)

            # Include file if it's not in platforms or if it's in an inclusion directory
            if not in_platforms or in_inclusion:
                sources.append(file_path)
                _locked_print(f"Including source: {rel_path}")
            else:
                _locked_print(f"Skipping source: {rel_path}")

    return sources


def _clean_obj_files(build_dir: Path) -> None:
    """
    Clean up object files in the build directory.
    This function removes all .o files in the specified directory.
    """
    if build_dir.is_dir():
        for obj_file in build_dir.glob("*.o"):
            _locked_print(f"Removing object file: {obj_file}")
            obj_file.unlink()
    else:
        _locked_print(
            f"Build directory '{build_dir}' does not exist. Skipping cleanup."
        )


def build_static_lib(
    src_dir: Path,
    build_dir: Path,
    build_mode: BuildMode = BuildMode.QUICK,
    max_workers: int | None = None,
) -> None:
    if not src_dir.is_dir():
        _locked_print(f"Error: '{src_dir}' is not a directory.")
        sys.exit(1)

    _clean_obj_files(build_dir)

    max_workers = (max_workers or _get_cpu_count()) * 2
    lib_path = build_dir / "libfastled.a"
    sources = filter_sources(src_dir)

    include_flags = [f"-I{src_dir.resolve()}", "-I."]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_src = {
            executor.submit(
                compile_source_to_obj, f, src_dir, build_dir, include_flags, build_mode
            ): f
            for f in sources
        }

        obj_files = []
        for future in as_completed(future_to_src):
            try:
                obj_files.append(future.result())
            except subprocess.CalledProcessError as e:
                _locked_print(f"❌ Failed to compile {future_to_src[future]}: {e}")
                raise

    if lib_path.exists():
        lib_path.unlink()

    cmd = [AR, "rcT", str(lib_path)] + [str(obj) for obj in obj_files]
    cmd_str = subprocess.list2cmdline(cmd)
    _locked_print(f"Archiving (thin): {cmd_str}")
    subprocess.check_call(cmd)

    _locked_print(f"\n✅ Static library created: {lib_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build static .a library from source files."
    )
    parser.add_argument(
        "--src",
        type=Path,
        required=True,
        help="Source directory containing .cpp/.ino files",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for .o and .a files"
    )

    # Build mode arguments (mutually exclusive)
    build_mode_group = parser.add_mutually_exclusive_group()
    build_mode_group.add_argument(
        "--debug", action="store_true", help="Build with debug flags (default)"
    )
    build_mode_group.add_argument(
        "--quick", action="store_true", help="Build with light optimization (O1)"
    )
    build_mode_group.add_argument(
        "--release", action="store_true", help="Build with aggressive optimization (Oz)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Determine build mode
    if args.release:
        build_mode = BuildMode.RELEASE
    elif args.quick:
        build_mode = BuildMode.QUICK
    else:
        # Default to debug if no mode specified
        build_mode = BuildMode.DEBUG

    _locked_print(f"Building with mode: {build_mode.name}")
    _locked_print(f"Including directories: {_INCLUSION_DIRS}")
    build_static_lib(args.src, args.out, build_mode)
    _PRINT_QUEUE.put(None)  # Signal the print worker to exit
    # _PRINT_QUEUE.join()  # Wait for all queued prints to finish
    _THREADED_PRINT.join()  # Wait for the print worker to finish
