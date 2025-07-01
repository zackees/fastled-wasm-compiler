import argparse
import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler.paths import BUILD_ROOT, FASTLED_SRC

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
    "-DFASTLED_WASM_USE_CCALL",
    "-DGL_ENABLE_GET_PROC_ADDRESS=0",
    "-std=gnu++17",
    "-fpermissive",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    "-Werror=cast-function-type",
    # Threading disabled flags
    "-fno-threadsafe-statics",  # Disable thread-safe static initialization
    "-DEMSCRIPTEN_NO_THREADS",  # Define to disable threading
    "-D_REENTRANT=0",  # Disable reentrant code
    "-I.",
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
    "-flto=thin",
    "-O0",
    "-sASSERTIONS=0",
    "-g0",
    "-fno-inline-functions",
    "-fno-vectorize",
    "-fno-unroll-loops",
    "-fno-strict-aliasing",
]

# Default to debug flags
# Base compile flags (used during compilation)
CXX_FLAGS = BASE_CXX_FLAGS

# Base link flags (used during linking)
BASE_LINK_FLAGS = [
    "-fuse-ld=lld",
    "-sWASM=1",
    "--no-entry",
    "--emit-symbol-map",
    "-sMODULARIZE=1",
    "-sEXPORT_NAME=fastled",
    "-sUSE_PTHREADS=0",
    "-sEXIT_RUNTIME=0",
    # Emscripten-specific linker settings
    "-sALLOW_MEMORY_GROWTH=1",
    "-sINITIAL_MEMORY=134217728",
    "-sAUTO_NATIVE_LIBRARIES=0",
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8','HEAPU8','getValue']",
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files','_getStripPixelData']",
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
LINK_FLAGS = [*BASE_LINK_FLAGS, *DEBUG_LINK_FLAGS, "-o", "fastled.js"]


def compile_cpp_to_obj(
    src_file: Path,
    build_mode: str,
) -> tuple[subprocess.CompletedProcess, Path]:
    build_dir = BUILD_ROOT / build_mode.lower()
    obj_file = build_dir / f"{src_file.stem}.o"
    os.makedirs(build_dir, exist_ok=True)

    flags = CXX_FLAGS
    mode_flags = []
    if build_mode.lower() == "debug":
        mode_flags = DEBUG_CXX_FLAGS
        flags += DEBUG_CXX_FLAGS
    elif build_mode.lower() == "quick":
        mode_flags = QUICK_CXX_FLAGS
        flags += QUICK_CXX_FLAGS
    elif build_mode.lower() == "release":
        mode_flags = ["-Oz"]
        flags += ["-Oz"]
    
    print(f"    📄 {src_file.name} → {obj_file.name}")
    print(f"    🔧 Mode-specific flags: {' '.join(mode_flags) if mode_flags else 'none'}")

    # cmd = [CXX, "-o", obj_file.as_posix(), *flags, str(src_file)]
    cmd: list[str] = []
    cmd.extend([CXX])
    cmd.append("-c")
    cmd.extend(["-x", "c++"])
    cmd.extend(["-o", obj_file.as_posix()])
    cmd.extend(flags)
    cmd.append(str(src_file))

    print("    Compiling:", subprocess.list2cmdline(cmd))
    # subprocess.check_call(cmd)
    cp = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
    )
    return (cp, obj_file)


def compile_sketch(sketch_dir: Path, build_mode: str) -> Exception | None:
    # Determine output directory first
    output_dir = BUILD_ROOT / build_mode.lower()
    
    print(f"\n🚀 Starting FastLED sketch compilation (no-platformio mode)")
    print(f"📁 Sketch directory: {sketch_dir}")
    print(f"🔧 Build mode: {build_mode}")
    print(f"📂 Output directory: {output_dir}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    print(f"✓ Output directory prepared: {output_dir}")

    # Add separate dwarf file for debug mode
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        LINK_FLAGS.append(f"-gseparate-dwarf={dwarf_file}")
        print(f"🐛 Debug mode: DWARF debug info will be generated at {dwarf_file}")

    # Gather all .cpp and .ino files in sketch dir
    sources = list(sketch_dir.glob("*.cpp")) + list(sketch_dir.glob("*.ino"))
    if not sources:
        raise RuntimeError(f"No .cpp or .ino files found in {sketch_dir}")
    
    print(f"\n📋 Source file discovery:")
    print(f"✓ Found {len(sources)} source file(s):")
    for i, src in enumerate(sources, 1):
        print(f"  {i}. {src.name} ({src.stat().st_size} bytes)")

    # Now print out the entire build flags group:
    print(f"\n🔧 Compilation configuration:")
    print("CXX_FLAGS:", " ".join(CXX_FLAGS))
    print("LINK_FLAGS:", " ".join(LINK_FLAGS))
    print("Sources:", " ".join(str(s) for s in sources))
    print("Sketch directory:", sketch_dir)
    
    # Determine which FastLED library to link against
    lib_path = f"/build/{build_mode.lower()}/libfastled.a"
    print(f"📚 FastLED library: {lib_path}")
    
    if not Path(lib_path).exists():
        print(f"⚠️  Warning: FastLED library not found at {lib_path}")
    else:
        lib_size = Path(lib_path).stat().st_size
        print(f"✓ FastLED library found ({lib_size} bytes)")

    obj_files: list[Path] = []
    print(f"\n🔨 Compiling source files:")
    for i, src_file in enumerate(sources, 1):
        print(f"\n  [{i}/{len(sources)}] Compiling {src_file.name}...")
        cp: subprocess.CompletedProcess
        obj_file: Path
        cp, obj_file = compile_cpp_to_obj(src_file, build_mode)
        if cp.returncode != 0:
            stdout = cp.stdout
            stderr = cp.stderr
            assert isinstance(stdout, bytes)
            assert isinstance(stderr, bytes)
            print(f"❌ Error compiling {src_file}:")
            print(f"stdout: {stdout.decode()}")
            print(f"stderr: {stderr.decode()}")
            return RuntimeError(f"Error compiling {src_file}: {stderr.decode()}")
        obj_size = obj_file.stat().st_size if obj_file.exists() else 0
        print(f"  ✓ {src_file.name} → {obj_file.name} ({obj_size} bytes)")
        obj_files.append(obj_file)

    # Link everything into one JS+WASM module
    output_js = output_dir / "fastled.js"
    output_wasm = output_dir / "fastled.wasm"
    # cmd_link = [CC, *LINK_FLAGS, *map(str, obj_files)]
    # cmd_link[cmd_link.index("-o") + 1] = str(output_js)

    print(f"\n🔗 Linking phase:")
    print(f"✓ Linking {len(obj_files)} object file(s) into final output")
    
    total_obj_size = sum(obj.stat().st_size for obj in obj_files if obj.exists())
    print(f"✓ Total object file size: {total_obj_size} bytes")

    cmd_link: list[str] = []
    cmd_link.extend([CXX])
    cmd_link.extend(LINK_FLAGS)
    cmd_link.extend(map(str, obj_files))
    if build_mode.lower() == "debug":
        cmd_link.append("/build/debug/libfastled.a")
        print(f"🐛 Linking with debug FastLED library: /build/debug/libfastled.a")
    elif build_mode.lower() == "release":
        cmd_link.append("/build/release/libfastled.a")
        print(f"🚀 Linking with release FastLED library: /build/release/libfastled.a")
    elif build_mode.lower() == "quick":
        cmd_link.append("/build/quick/libfastled.a")
        print(f"⚡ Linking with quick FastLED library: /build/quick/libfastled.a")
    else:
        raise ValueError(f"Invalid build mode: {build_mode}")
    cmd_link[cmd_link.index("-o") + 1] = str(output_js)
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        cmd_link.append(f"-gseparate-dwarf={dwarf_file}")

    print("\nLinking:", subprocess.list2cmdline(cmd_link))
    print(f"📤 Output JavaScript: {output_js}")
    print(f"📤 Output WebAssembly: {output_wasm}")
    
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
        print(f"❌ Error linking {output_js}:")
        print(f"stdout: {stdout.decode()}")
        print(f"stderr: {stderr.decode()}")
        return RuntimeError(f"Error linking {output_js}: {stderr.decode()}")

    # Check and report output file sizes
    if output_js.exists():
        js_size = output_js.stat().st_size
        print(f"✅ JavaScript output: {output_js} ({js_size} bytes)")
    else:
        print(f"⚠️  JavaScript output not found: {output_js}")
        
    if output_wasm.exists():
        wasm_size = output_wasm.stat().st_size
        print(f"✅ WebAssembly output: {output_wasm} ({wasm_size} bytes)")
    else:
        print(f"⚠️  WebAssembly output not found: {output_wasm}")
        
    # Check for debug files in debug mode
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        if dwarf_file.exists():
            dwarf_size = dwarf_file.stat().st_size
            print(f"🐛 Debug info: {dwarf_file} ({dwarf_size} bytes)")
        else:
            print(f"⚠️  Debug info not found: {dwarf_file}")

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
