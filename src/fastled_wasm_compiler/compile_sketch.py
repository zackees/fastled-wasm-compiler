import argparse
import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR = FASTLED_SRC.as_posix()

CC = "em++"

# Base flags from platformio.ini [env:wasm-base]
BASE_CXX_FLAGS = [
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
    "-DFASTLED_FORCE_NAMESPACE=1",
    "-DFASTLED_USE_PROGMEM=0",
    "-DUSE_OFFSET_CONVERTER=0",
    "-DSKETCH_COMPILE=1",
    "-std=gnu++17",
    "-fpermissive",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    "-Werror=cast-function-type",
    "-Isrc",
    f"-I{FASTLED_SRC_STR}",
    f"-I{FASTLED_SRC_STR}/platforms/wasm/compiler",
]

# Debug flags from platformio.ini [env:wasm-debug]
DEBUG_CXX_FLAGS = [
    "-g3",
    "-gsource-map",
    "-ffile-prefix-map=/=sketchsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-O0",
]

# Quick build flags from platformio.ini [env:wasm-quick]
QUICK_CXX_FLAGS = [
    "-O0",
    "-sASSERTIONS=0",
    "-g0",
    "-fno-inline-functions",
    "-fno-vectorize",
    "-fno-unroll-loops",
    "-fno-strict-aliasing",
]

# Default to debug flags
CXX_FLAGS = BASE_CXX_FLAGS + DEBUG_CXX_FLAGS

# Base link flags from platformio.ini
BASE_LINK_FLAGS = [
    "--bind",
    "-fuse-ld=lld",
    "-sWASM=1",
    "-sALLOW_MEMORY_GROWTH=1",
    "-sINITIAL_MEMORY=134217728",
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8']",
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files']",
    "--no-entry",
    "--emit-symbol-map",
    "-sMODULARIZE=1",
    "-sEXPORT_NAME=fastled",
    "-sUSE_PTHREADS=0",
    "-sEXIT_RUNTIME=0",
    "-sFILESYSTEM=0",
    "-Wl,--whole-archive",
    "--source-map-base=http://localhost:8000/",
]

# Debug link flags
DEBUG_LINK_FLAGS = [
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-sSEPARATE_DWARF_URL=fastled.wasm.dwarf",
    "-sSTACK_OVERFLOW_CHECK=2",
    "-sASSERTIONS=1",
]

# Default to debug link flags
LINK_FLAGS = BASE_LINK_FLAGS + DEBUG_LINK_FLAGS + ["-o", "fastled.js"]


def compile_cpp_to_obj(
    src_file: Path, build_dir: Path, include_dirs: list[str]
) -> Path:
    obj_file = build_dir / f"{src_file.stem}.o"
    os.makedirs(build_dir, exist_ok=True)

    include_flags = [f"-I{d}" for d in include_dirs]
    cmd = [CC, "-o", str(obj_file), "-c", *CXX_FLAGS, *include_flags, str(src_file)]
    print("Compiling:", " ".join(cmd))
    subprocess.check_call(cmd)
    return obj_file


def compile_sketch(
    sketch_dir: Path, lib_path: Path, output_dir: Path, build_mode: str = "debug"
):
    os.makedirs(output_dir, exist_ok=True)

    # Set build flags based on mode
    global CXX_FLAGS, LINK_FLAGS
    if build_mode.lower() == "quick":
        CXX_FLAGS = BASE_CXX_FLAGS + QUICK_CXX_FLAGS
        LINK_FLAGS = BASE_LINK_FLAGS + ["-sASSERTIONS=0", "-o", "fastled.js"]
    elif build_mode.lower() == "release":
        CXX_FLAGS = BASE_CXX_FLAGS + ["-Oz"]
        LINK_FLAGS = BASE_LINK_FLAGS + ["-sASSERTIONS=0", "-o", "fastled.js"]
    else:  # debug is default
        CXX_FLAGS = BASE_CXX_FLAGS + DEBUG_CXX_FLAGS
        LINK_FLAGS = BASE_LINK_FLAGS + DEBUG_LINK_FLAGS + ["-o", "fastled.js"]

    # Add separate dwarf file for debug mode
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        LINK_FLAGS.append(f"-gseparate-dwarf={dwarf_file}")

    # Gather all .cpp and .ino files in sketch dir
    sources = list(sketch_dir.glob("*.cpp")) + list(sketch_dir.glob("*.ino"))
    if not sources:
        raise RuntimeError(f"No .cpp or .ino files found in {sketch_dir}")

    # Compile all to object files
    include_dirs = [sketch_dir, ".", FASTLED_SRC_STR]
    obj_files = [compile_cpp_to_obj(f, output_dir, include_dirs) for f in sources]

    # Link everything into one JS+WASM module
    output_js = output_dir / "fastled.js"
    cmd_link = [CC, *LINK_FLAGS, *map(str, obj_files), str(lib_path)]
    cmd_link[cmd_link.index("-o") + 1] = str(output_js)

    print("Linking:", " ".join(cmd_link))
    subprocess.check_call(cmd_link)

    print(f"\n✅ Program built at: {output_js}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compile a FastLED sketch into WASM using a static lib."
    )
    parser.add_argument(
        "--example",
        type=Path,
        required=True,
        help="Directory with example source files",
    )
    parser.add_argument("--lib", type=Path, required=True, help="Path to libfastled.a")
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for build artifacts"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["debug", "quick", "release"],
        default="debug",
        help="Build mode: debug, quick, or release (default: debug)",
    )

    args = parser.parse_args()
    compile_sketch(args.example, args.lib, args.out, args.mode)
