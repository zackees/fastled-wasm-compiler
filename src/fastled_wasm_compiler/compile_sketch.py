import argparse
import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR = FASTLED_SRC.as_posix()

CC = "/build_tools/ccache-emcc.sh"
CXX = "/build_tools/ccache-emcxx.sh"

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
CXX_FLAGS = BASE_CXX_FLAGS

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
    src_file: Path,
    build_mode: str,
) -> tuple[subprocess.CompletedProcess, Path]:
    build_dir = Path("/js/build") / build_mode.lower()
    obj_file = build_dir / f"{src_file.stem}.o"
    os.makedirs(build_dir, exist_ok=True)

    flags = CXX_FLAGS
    if build_mode.lower() == "debug":
        flags += DEBUG_CXX_FLAGS
    elif build_mode.lower() == "quick":
        flags += QUICK_CXX_FLAGS
    elif build_mode.lower() == "release":
        flags += ["-Oz"]

    # cmd = [CXX, "-o", obj_file.as_posix(), *flags, str(src_file)]
    cmd: list[str] = []
    cmd.extend([CXX])
    cmd.append("-c")
    cmd.extend(["-x", "c++"])
    cmd.extend(["-o", obj_file.as_posix()])
    cmd.extend(flags)
    cmd.append(str(src_file))

    print("\nCompiling:", subprocess.list2cmdline(cmd))
    # subprocess.check_call(cmd)
    cp = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
    )
    return (cp, obj_file)


def compile_sketch(sketch_dir: Path, build_mode: str) -> Exception | None:
    # Add separate dwarf file for debug mode
    if build_mode.lower() == "debug":
        dwarf_file = Path("/build/debug/fastled.wasm.dwarf")
        LINK_FLAGS.append(f"-gseparate-dwarf={dwarf_file}")

    # Gather all .cpp and .ino files in sketch dir
    sources = list(sketch_dir.glob("*.cpp")) + list(sketch_dir.glob("*.ino"))
    if not sources:
        raise RuntimeError(f"No .cpp or .ino files found in {sketch_dir}")

    # Now print out the entire build flags group:
    print("CXX_FLAGS:", " ".join(CXX_FLAGS))
    print("LINK_FLAGS:", " ".join(LINK_FLAGS))
    print("Sources:", " ".join(str(s) for s in sources))
    print("Sketch directory:", sketch_dir)

    obj_files: list[Path] = []
    for src_file in sources:
        cp: subprocess.CompletedProcess
        obj_file: Path
        cp, obj_file = compile_cpp_to_obj(src_file, build_mode)
        if cp.returncode != 0:
            stdout = cp.stdout
            stderr = cp.stderr
            assert isinstance(stdout, bytes)
            assert isinstance(stderr, bytes)
            print(f"Error compiling {src_file}:")
            print(f"stdout: {stdout.decode()}")
            print(f"stderr: {stderr.decode()}")
            return RuntimeError(f"Error compiling {src_file}: {stderr.decode()}")
        print(f"Compiled {src_file} to {obj_file}")
        obj_files.append(obj_file)

    output_dir = Path("/js/build") / build_mode.lower()
    # Link everything into one JS+WASM module
    output_js = output_dir / "fastled.js"
    # cmd_link = [CC, *LINK_FLAGS, *map(str, obj_files)]
    # cmd_link[cmd_link.index("-o") + 1] = str(output_js)

    cmd_link: list[str] = []
    cmd_link.extend([CXX])
    cmd_link.extend(LINK_FLAGS)
    cmd_link.extend(map(str, obj_files))
    if build_mode.lower() == "debug":
        cmd_link.append("/build/debug/libfastled.a")
    elif build_mode.lower() == "release":
        cmd_link.append("/build/release/libfastled.a")
    elif build_mode.lower() == "quick":
        cmd_link.append("/build/quick/libfastled.a")
    else:
        raise ValueError(f"Invalid build mode: {build_mode}")
    cmd_link[cmd_link.index("-o") + 1] = str(output_js)
    if build_mode.lower() == "debug":
        dwarf_file = Path("/build/debug/fastled.wasm.dwarf")
        cmd_link.append(f"-gseparate-dwarf={dwarf_file}")

    print("\nLinking:", subprocess.list2cmdline(cmd_link))
    # subprocess.check_call(cmd_link)
    cp = subprocess.run(
        cmd_link,
        check=False,
        capture_output=True,
    )
    if cp.returncode != 0:
        stdout = cp.stdout
        stderr = cp.stderr
        assert isinstance(stdout, bytes)
        assert isinstance(stderr, bytes)
        print(f"Error linking {output_js}:")
        print(f"stdout: {stdout.decode()}")
        print(f"stderr: {stderr.decode()}")
        return RuntimeError(f"Error linking {output_js}: {stderr.decode()}")

    print(f"\n✅ Program built at: {output_js}")
    return None


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a FastLED sketch into WASM using a static lib."
    )
    parser.add_argument(
        "--sketch",
        type=Path,
        required=True,
        help="Directory with example source files",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["debug", "quick", "release"],
        default="debug",
        help="Build mode: debug, quick, or release (default: debug)",
    )

    args = parser.parse_args()

    err = compile_sketch(args.sketch, args.mode)
    if isinstance(err, Exception):
        print(f"Compilation error: {err}")
        return 1
    assert err is None, f"Error was not None: {err}"
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main())
