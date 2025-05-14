import argparse
import os
import subprocess
from pathlib import Path

CC = "em++"

CXX_FLAGS = [
    "-std=gnu++17",
    "-fpermissive",
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
    "-DFASTLED_FORCE_NAMESPACE=1",
    "-DFASTLED_USE_PROGMEM=0",
    "-DFASTLED_FORCE_USE_NAMESPACE=1",
    "-DUSE_OFFSET_CONVERTER=0",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    "-Werror=cast-function-type",
    "-g3",
    "-gsource-map",
    "-ffile-prefix-map=/=sketchsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-O0",
    "-I/headers",
]

LINK_FLAGS = [
    "--bind",
    "-fuse-ld=lld",
    "-sWASM=1",
    "-sALLOW_MEMORY_GROWTH=1",
    "-sINITIAL_MEMORY=134217728",
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8']",
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files']",
    "--no-entry",
    "--emit-symbol-map",
    "-gseparate-dwarf=fastled.wasm.dwarf",
    "-sSEPARATE_DWARF_URL=fastled.wasm.dwarf",
    "-sSTACK_OVERFLOW_CHECK=2",
    "-sASSERTIONS=1",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-sMODULARIZE=1",
    "-sEXPORT_NAME=fastled",
    "-o",
    "fastled.js",
    "--source-map-base=http://localhost:8000/",
]


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


def compile_sketch(sketch_dir: Path, lib_path: Path, output_dir: Path):
    os.makedirs(output_dir, exist_ok=True)

    # Gather all .cpp and .ino files in sketch dir
    sources = list(sketch_dir.glob("*.cpp")) + list(sketch_dir.glob("*.ino"))
    if not sources:
        raise RuntimeError(f"No .cpp or .ino files found in {sketch_dir}")

    # Compile all to object files
    include_dirs = [sketch_dir, ".", "/headers"]
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

    args = parser.parse_args()
    compile_sketch(args.example, args.lib, args.out)
