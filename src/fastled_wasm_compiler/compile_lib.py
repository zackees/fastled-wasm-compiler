import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CC = "em++"
AR = "emar"

CXX_FLAGS = [
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
    "-g3",
    "-gsource-map",
    "-ffile-prefix-map=/=drawfsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-O0",
]


def compile_cpp_to_obj(src_file: Path, out_dir: Path, include_flags: list[str]) -> Path:
    obj_file = out_dir / (src_file.stem + ".o")
    os.makedirs(out_dir, exist_ok=True)
    cmd = [CC, "-o", str(obj_file), "-c", *CXX_FLAGS, *include_flags, str(src_file)]
    print("Compiling:", " ".join(cmd))
    subprocess.check_call(cmd)
    return obj_file


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


def build_static_lib(
    src_dir: Path, build_dir: Path, max_workers: int | None = None
) -> None:
    max_workers = max_workers or _get_cpu_count()
    lib_path = build_dir / "libfastled.a"
    sources = list(src_dir.rglob("*.cpp")) + list(src_dir.rglob("*.ino"))

    include_flags = [f"-I{src_dir.resolve()}", "-I."]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_src = {
            executor.submit(compile_cpp_to_obj, f, build_dir, include_flags): f
            for f in sources
        }

        obj_files = []
        for future in as_completed(future_to_src):
            try:
                obj_files.append(future.result())
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to compile {future_to_src[future]}: {e}")
                raise

    if lib_path.exists():
        lib_path.unlink()

    cmd = [AR, "rcs", str(lib_path)] + [str(obj) for obj in obj_files]
    print("Archiving:", " ".join(cmd))
    subprocess.check_call(cmd)

    print(f"\n✅ Static library created: {lib_path}")


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
    args = parser.parse_args()
    build_static_lib(args.src, args.out)
