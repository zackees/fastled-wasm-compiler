"""
Direct emscripten toolchain compilation bypassing platformio.

This module provides functions to compile sketches directly using emscripten tools,
which is faster and more reliable than using platformio for WASM compilation.
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

from fastled_wasm_compiler.paths import BUILD_ROOT, get_fastled_source_path

# --------------------------------------------------------------------------------------
# Helper function
# --------------------------------------------------------------------------------------
# NOTE: We want to stream compiler/linker output _as it happens_ instead of buffering the
# entire output and printing it afterwards.  This helper runs the given command with
# `subprocess.Popen`, merges stdout/stderr, prints each line immediately (prefixed for
# context), then returns a `subprocess.CompletedProcess` so callers can still inspect the
# captured output and return-code just like they did with `subprocess.run`.


def _run_cmd_and_stream(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run command and return the completed process.

    Args:
        cmd: Command split into a list suitable for *subprocess*.

    Returns:
        A subprocess.CompletedProcess with stdout and the process' exit code.
    """
    return subprocess.run(cmd, capture_output=True, text=True)


# Use environment-variable driven FastLED source path
# In Docker container, this should be set to "/git/fastled/src"
# On host system, this will use the default from paths.py
FASTLED_SRC_STR = get_fastled_source_path()

# Ensure it's an absolute path for Docker container
if not FASTLED_SRC_STR.startswith("/"):
    FASTLED_SRC_STR = f"/{FASTLED_SRC_STR}"

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
    f"-fuse-ld={os.environ.get('LINKER', 'lld')}",  # Configurable linker
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
    "-Wl,--gc-sections",
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


def analyze_source_for_pch_usage(src_file: Path) -> Tuple[bool, bool]:
    """
    Analyze a source file to determine if we can use precompiled headers.
    If we can use PCH and headers need to be removed, modifies the file in place.

    Returns:
        (can_use_pch, headers_removed):
        - can_use_pch: True if we can inject PCH (no defines before FastLED.h)
        - headers_removed: True if FastLED.h/Arduino.h includes were removed from the file
    """
    try:
        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Could not read {src_file}: {e}")
        return False, False

    lines = content.splitlines()

    # Track what we find
    fastled_include_line = None
    arduino_include_line = None
    has_defines_before_fastled = False

    # Scan through the file line by line
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check for FastLED.h include
        if re.match(r'^\s*#\s*include\s*[<"]FastLED\.h[>"]', line):
            fastled_include_line = i
            break  # Found FastLED.h, stop scanning

        # Check for Arduino.h include
        if re.match(r'^\s*#\s*include\s*[<"]Arduino\.h[>"]', line):
            arduino_include_line = i
            continue

        # Check for #define statements
        if re.match(r"^\s*#\s*define\s+", line):
            has_defines_before_fastled = True
            continue

        # Check for other preprocessor directives that might affect compilation
        if re.match(r"^\s*#\s*(ifdef|ifndef|if|pragma)", line):
            has_defines_before_fastled = True
            continue

    # If no FastLED.h found, we can't use PCH
    if fastled_include_line is None:
        return False, False

    # If there are defines before FastLED.h, we can't safely use PCH
    if has_defines_before_fastled:
        return False, False

    # We can use PCH! Check if we need to remove headers
    headers_to_remove = []
    if fastled_include_line is not None:
        headers_to_remove.append(fastled_include_line)
    if arduino_include_line is not None:
        headers_to_remove.append(arduino_include_line)

    if not headers_to_remove:
        # Can use PCH but no headers to remove
        return True, False

    # Remove headers (in reverse order to maintain line numbers)
    modified_lines = lines.copy()
    for line_num in sorted(headers_to_remove, reverse=True):
        del modified_lines[line_num]

    # Write the modified content back to the file
    try:
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("\n".join(modified_lines))
        return True, True
    except Exception as e:
        print(f"Warning: Could not modify {src_file}: {e}")
        return False, False


def compile_cpp_to_obj(
    src_file: Path,
    build_mode: str,
) -> tuple[subprocess.CompletedProcess, Path, str]:
    build_dir = BUILD_ROOT / build_mode.lower()
    obj_file = build_dir / f"{src_file.stem}.o"
    os.makedirs(build_dir, exist_ok=True)

    # Work on a copy so we don't mutate shared global defaults
    flags = list(CXX_FLAGS)
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

    # Build output messages for later display
    output_lines = []
    output_lines.append(f"    📄 {src_file.name} → {obj_file.name}")
    output_lines.append(
        f"    🔧 Mode-specific flags: {' '.join(mode_flags) if mode_flags else 'none'}"
    )

    # Analyze source file for intelligent PCH usage (only available in QUICK mode)
    pch_file = build_dir / "fastled_pch.h"

    if build_mode.lower() == "quick" and pch_file.exists():
        can_use_pch, headers_removed = analyze_source_for_pch_usage(src_file)

        if can_use_pch:
            # Use PCH
            flags.extend(["-include", str(pch_file)])
            output_lines.append(
                f"    🚀 PCH OPTIMIZATION APPLIED: Using precompiled header {pch_file.name}"
            )

            if headers_removed:
                output_lines.append(
                    "    ✂️  PCH OPTIMIZATION: Removed FastLED.h/Arduino.h includes from source"
                )

            output_lines.append(
                "    ⚡ PCH OPTIMIZATION: Compilation should be faster!"
            )
        else:
            # Cannot use PCH due to defines before FastLED.h
            output_lines.append(
                "    ⚠️  PCH OPTIMIZATION SKIPPED: defines found before FastLED.h include"
            )
            output_lines.append(
                "    💡 PCH TIP: Move #define statements after #include <FastLED.h> for faster builds"
            )
    elif build_mode.lower() == "quick":
        output_lines.append(
            f"    ⚠️  PCH OPTIMIZATION UNAVAILABLE: Precompiled header not found at {pch_file}"
        )
        output_lines.append(
            "    💡 PCH TIP: Build the FastLED library first to generate precompiled headers"
        )
    else:
        output_lines.append(
            "    ℹ️  PCH OPTIMIZATION DISABLED: Precompiled headers only available in QUICK mode"
        )

    # cmd = [CXX, "-o", obj_file.as_posix(), *flags, str(src_file)]
    cmd: list[str] = []
    cmd.extend([CXX])
    cmd.append("-c")
    cmd.extend(["-x", "c++"])
    cmd.extend(["-o", obj_file.as_posix()])
    cmd.extend(flags)
    cmd.append(str(src_file))

    output_lines.append("    🔨 Compiling with command:")
    output_lines.append(f"    {subprocess.list2cmdline(cmd)}")
    output_lines.append("    📤 Compiler output:")

    # Run compilation and capture output
    cp = _run_cmd_and_stream(cmd)

    # Add compiler output to our captured lines
    if cp.stdout:
        for line in cp.stdout.splitlines():
            output_lines.append(f"    [emcc] {line}")
    if cp.stderr:
        for line in cp.stderr.splitlines():
            output_lines.append(f"    [emcc] {line}")

    if cp.returncode == 0:
        output_lines.append(f"    ✅ Successfully compiled {src_file.name}")
    else:
        output_lines.append(
            f"    ❌ Failed to compile {src_file.name} (exit code: {cp.returncode})"
        )

    return (cp, obj_file, "\n".join(output_lines))


def compile_sketch(sketch_dir: Path, build_mode: str) -> Exception | None:
    # Determine output directory first
    output_dir = BUILD_ROOT / build_mode.lower()

    print("\n🚀 Starting FastLED sketch compilation (no-platformio mode)")
    print("🔊 VERBOSE MODE: Showing detailed emcc/linker output")
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

    print("\n📋 Source file discovery:")
    print(f"✓ Found {len(sources)} source file(s):")
    for i, src in enumerate(sources, 1):
        print(f"  {i}. {src.name} ({src.stat().st_size} bytes)")

    # Now print out the entire build flags group:
    print("\n🔧 Compilation configuration:")
    print("📋 CXX_FLAGS:")
    for i, flag in enumerate(CXX_FLAGS):
        print(f"  {i+1:2d}. {flag}")
    print("\n📋 LINK_FLAGS:")
    for i, flag in enumerate(LINK_FLAGS):
        print(f"  {i+1:2d}. {flag}")
    print(f"\n📋 Sources: {' '.join(str(s) for s in sources)}")
    print(f"📋 Sketch directory: {sketch_dir}")

    # Determine which FastLED library to link against - explicit choice based on NO_THIN_LTO
    no_thin_lto = os.environ.get("NO_THIN_LTO", "0") == "1"

    if no_thin_lto:
        # NO_THIN_LTO=1: Explicitly use regular archives
        lib_path = BUILD_ROOT / build_mode.lower() / "libfastled.a"
        print("NO_THIN_LTO=1: Using regular archive")
    else:
        # NO_THIN_LTO=0 or unset: Explicitly use thin archives
        lib_path = BUILD_ROOT / build_mode.lower() / "libfastled-thin.a"
        print("NO_THIN_LTO=0: Using thin archive")

    print(f"\n📚 FastLED library: {lib_path}")

    if not lib_path.exists():
        print(f"⚠️  Warning: FastLED library not found at {lib_path}")
    else:
        lib_size = lib_path.stat().st_size
        archive_type = "thin" if "thin" in lib_path.name else "regular"
        print(f"✓ FastLED library found ({lib_size} bytes, {archive_type} archive)")

    obj_files: list[Path] = []
    print(f"\n🔨 Compiling {len(sources)} source files in parallel:")
    print("=" * 80)

    # Use ThreadPoolExecutor to compile files in parallel
    max_workers = min(len(sources), os.cpu_count() or 4)  # Limit to available CPUs
    print(f"🔧 Using {max_workers} worker threads for parallel compilation")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all compilation tasks
        future_to_src = {
            executor.submit(compile_cpp_to_obj, src_file, build_mode): src_file
            for src_file in sources
        }

        # Process completed compilations as they finish
        completed_count = 0

        try:
            for future in as_completed(future_to_src):
                src_file = future_to_src[future]
                completed_count += 1

                try:
                    cp, obj_file, output = future.result()

                    # Print the captured output from this compilation
                    print(
                        f"\n  📝 [{completed_count}/{len(sources)}] Compilation details for {src_file.name}:"
                    )
                    print(output)

                    if cp.returncode != 0:
                        print(f"❌ Error compiling {src_file}:")
                        # Cancel all remaining futures
                        for remaining_future in future_to_src:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        print("🛑 Cancelling remaining compilation tasks...")
                        return RuntimeError(
                            f"Error compiling {src_file}: Compilation failed with exit code {cp.returncode}"
                        )
                    obj_size = obj_file.stat().st_size if obj_file.exists() else 0
                    print(
                        f"  ✓ [{completed_count}/{len(sources)}] {src_file.name} → {obj_file.name} ({obj_size} bytes)"
                    )
                    obj_files.append(obj_file)
                except Exception as e:
                    print(f"❌ Exception during compilation of {src_file}: {e}")

                    # Cancel all remaining futures
                    for remaining_future in future_to_src:
                        if not remaining_future.done():
                            remaining_future.cancel()
                    print("🛑 Cancelling remaining compilation tasks...")
                    return RuntimeError(
                        f"Exception during compilation of {src_file}: {e}"
                    )
        except KeyboardInterrupt:
            print("🛑 Compilation interrupted by user, cancelling all tasks...")
            # Cancel all futures on keyboard interrupt
            for future in future_to_src:
                future.cancel()
            raise

    print("-" * 80)
    print(f"✅ All {len(sources)} source files compiled successfully")

    # Link everything into one JS+WASM module
    output_js = output_dir / "fastled.js"
    output_wasm = output_dir / "fastled.wasm"

    print("\n🔗 Linking phase - Creating final WASM output:")
    print("=" * 80)
    print(f"✓ Linking {len(obj_files)} object file(s) into final output")

    total_obj_size = sum(obj.stat().st_size for obj in obj_files if obj.exists())
    print(f"✓ Total object file size: {total_obj_size} bytes")

    cmd_link: list[str] = []
    cmd_link.extend([CXX])
    cmd_link.extend(LINK_FLAGS)
    cmd_link.extend(map(str, obj_files))

    # Use explicit archive selection based on NO_THIN_LTO (no fallback)
    no_thin_lto = os.environ.get("NO_THIN_LTO", "0") == "1"

    if build_mode.lower() == "debug":
        if no_thin_lto:
            debug_lib = BUILD_ROOT / "debug" / "libfastled.a"
        else:
            debug_lib = BUILD_ROOT / "debug" / "libfastled-thin.a"
        cmd_link.append(str(debug_lib))
        archive_type = "regular" if no_thin_lto else "thin"
        print(f"🐛 Linking with debug FastLED library: {debug_lib} ({archive_type})")
    elif build_mode.lower() == "release":
        if no_thin_lto:
            release_lib = BUILD_ROOT / "release" / "libfastled.a"
        else:
            release_lib = BUILD_ROOT / "release" / "libfastled-thin.a"
        cmd_link.append(str(release_lib))
        archive_type = "regular" if no_thin_lto else "thin"
        print(
            f"🚀 Linking with release FastLED library: {release_lib} ({archive_type})"
        )
    elif build_mode.lower() == "quick":
        if no_thin_lto:
            quick_lib = BUILD_ROOT / "quick" / "libfastled.a"
        else:
            quick_lib = BUILD_ROOT / "quick" / "libfastled-thin.a"
        cmd_link.append(str(quick_lib))
        archive_type = "regular" if no_thin_lto else "thin"
        print(f"⚡ Linking with quick FastLED library: {quick_lib} ({archive_type})")
    else:
        raise ValueError(f"Invalid build mode: {build_mode}")
    cmd_link[cmd_link.index("-o") + 1] = str(output_js)
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        cmd_link.append(f"-gseparate-dwarf={dwarf_file}")

    print("\n🔗 Linking with command:")
    print(f"{subprocess.list2cmdline(cmd_link)}")
    print(f"📤 Output JavaScript: {output_js}")
    print(f"📤 Output WebAssembly: {output_wasm}")
    print("📤 Linker output:")

    # Run linker and capture output
    cp = _run_cmd_and_stream(cmd_link)

    if cp.returncode != 0:
        print(f"❌ Error linking {output_js}:")
        print(f"Linker failed with exit code: {cp.returncode}")
        return RuntimeError(
            f"Error linking {output_js}: Linking failed with exit code {cp.returncode}"
        )
    else:
        print("✅ Linking completed successfully")

    print("=" * 80)

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
    print("🔊 VERBOSE BUILD COMPLETED: All emcc/linker calls shown above")
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
    sys.exit(_main())
