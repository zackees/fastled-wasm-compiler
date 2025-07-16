#!/usr/bin/env python3
# pylint: skip-file
# flake8: noqa
# type: ignore

"""
Flags that need to be imported into the platformio build.

This adds flags for a sketch to compile.
"""

import os
import shutil
from pathlib import Path

from SCons.Script import Import
from fastled_wasm_compiler.paths import get_fastled_source_path

_IS_GITHUB = os.environ.get("GITHUB_ACTIONS", "false") == "true"

# Use thin archive. Much faster.
# Use environment variable for build tools path with fallback
AR = os.environ.get("ENV_BUILD_TOOLS_DIR", "/build_tools") + "/emar-thin.sh"

# For drawf support it needs a file server running at this point.
# TODO: Emite this information as a src-map.json file to hold this
# port and other information.
SRC_SERVER_PORT = 8123
SRC_SERVER_HOST = f"http://localhost:{SRC_SERVER_PORT}"
SOURCE_MAP_BASE = f"--source-map-base={SRC_SERVER_HOST}"


# Determine whether to use ccache (recommended).
USE_CCACHE = True

# Get build mode from environment variable, default to QUICK if not set
BUILD_MODE = os.environ.get("BUILD_MODE", "QUICK").upper()
valid_modes = ["DEBUG", "QUICK", "RELEASE"]
if BUILD_MODE not in valid_modes:
    raise ValueError(f"BUILD_MODE must be one of {valid_modes}, got {BUILD_MODE}")

# Check if STRICT mode is enabled (treat warnings as errors)
STRICT_MODE = os.environ.get("STRICT", "").lower() in ("1", "true")

DEBUG = BUILD_MODE == "DEBUG"
QUICK_BUILD = BUILD_MODE == "QUICK"
OPTIMIZED = BUILD_MODE == "RELEASE"

# Choose WebAssembly (1), asm.js fallback (2)
USE_WASM = 2
if DEBUG or QUICK_BUILD:
    USE_WASM = 1

# Optimization level
# build_mode = "-O1" if QUICK_BUILD else "-Oz"

# Import environments
Import("env", "projenv")

# Build directory
BUILD_DIR = env.subst("$BUILD_DIR")
PROGRAM_NAME = "fastled"
OUTPUT_JS = f"{BUILD_DIR}/{PROGRAM_NAME}.js"

# Toolchain overrides to use Emscripten
CC = "ccache emcc" if USE_CCACHE else "emcc"
CXX = "ccache em++" if USE_CCACHE else "em++"
LINK = CXX
projenv.Replace(CC=CC, CXX=CXX, LINK=LINK, AR=AR, RANLIB="emranlib")
env.Replace(CC=CC, CXX=CXX, LINK=LINK, AR=AR, RANLIB="emranlib")


# Helper to strip out optimization flags
def _remove_flags(curr_flags: list[str], remove_flags: list[str]) -> list[str]:
    for flag in remove_flags:
        if flag in curr_flags:
            curr_flags.remove(flag)
    return curr_flags


# Paths for DWARF split
wasm_name = f"{PROGRAM_NAME}.wasm"

# Use environment-variable driven path for container compatibility
FASTLED_SRC_STR = get_fastled_source_path()

# Ensure it's an absolute path for Docker container
if not FASTLED_SRC_STR.startswith("/"):
    FASTLED_SRC_STR = f"/{FASTLED_SRC_STR}"

# Base compile flags (CCFLAGS/CXXFLAGS)
compile_flags = [
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50",
    "-DFASTLED_FORCE_NAMESPACE=1",
    "-DFASTLED_USE_PROGMEM=0",
    "-DUSE_OFFSET_CONVERTER=0",
    "-DGL_ENABLE_GET_PROC_ADDRESS=0",
    "-std=gnu++17",
    "-fpermissive",
    "-fno-rtti",
    "-fno-exceptions",
    "-Wno-constant-logical-operand",
    "-Wnon-c-typedef-for-linkage",
    "-Werror=bad-function-cast",
    "-Werror=cast-function-type",
    "-sERROR_ON_WASM_CHANGES_AFTER_LINK",
    "-emit-llvm",  # Generate LLVM bitcode for sketch compilation
    # Threading disabled flags
    "-fno-threadsafe-statics",  # Disable thread-safe static initialization
    "-DEMSCRIPTEN_NO_THREADS",  # Define to disable threading
    "-D_REENTRANT=0",  # Disable reentrant code
    "-I.",  # Add current directory to ensure quoted includes work same as angle bracket includes
    "-Isrc",
    f"-I{FASTLED_SRC_STR}",
    f"-I{FASTLED_SRC_STR}/platforms/wasm/compiler",
    # Add stricter compiler warnings.
    "-Wall",
]

# Additional warning flags to enable in strict mode
strict_warning_flags = [
    "-Wextra",
    "-Wconversion",
    "-Wsign-conversion",
    "-Wunused",
    "-Wuninitialized",
    "-Wdouble-promotion",
    "-Wformat=2",
    "-Wcast-align",
    "-Wcast-qual",
    "-Werror=return-type"
]

# Add strict mode flags if enabled
if STRICT_MODE:
    compile_flags.extend(["-Werror"] + strict_warning_flags)

# Base link flags (LINKFLAGS)
link_flags = [
    "-fuse-ld=lld",  # use LLD at link time
    f"-sWASM={USE_WASM}",  # Wasm vs asm.js
    "-sALLOW_MEMORY_GROWTH=1",  # enable dynamic heap growth
    "-sINITIAL_MEMORY=134217728",  # start with 128 MB heap
    "-sAUTO_NATIVE_LIBRARIES=0",
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8','HEAPU8','getValue']",
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files','_getStripPixelData']",
    # Threading disabled flags
    "-sUSE_PTHREADS=0",  # Disable POSIX threads
    "-sEXIT_RUNTIME=0",  # Don't exit runtime (not thread-related but often paired)
    "--no-entry",
]

# Debug-specific flags
debug_compile_flags = [
    "-g3",
    "-O0",
    "-gsource-map",
    # Files are mapped to dwarfsource when compiled, this allows us to use a
    # relative rather than absolute path which for some reason means it's
    # a network request instead of a disk request.
    # This enables the use of step through debugging.
    "-ffile-prefix-map=/=dwarfsource/",
    "-fsanitize=address",
    "-fsanitize=undefined",
    "-fno-inline",
    "-O0",
]


debug_link_flags = [
    "--emit-symbol-map",
    # write out the .dwarf file next to fastled.wasm
    f"-gseparate-dwarf={BUILD_DIR}/{wasm_name}.dwarf",
    # tell the JS loader where to fetch that .dwarf from at runtime (over HTTP)
    f"-sSEPARATE_DWARF_URL={wasm_name}.dwarf",
    # SOURCE_MAP_BASE,
    "-sSTACK_OVERFLOW_CHECK=2",
    "-sASSERTIONS=1",
    "-fsanitize=address",
    "-fsanitize=undefined",
]

# Adjust for QUICK_BUILD or DEBUG
if DEBUG:
    # strip default optimization levels
    compile_flags = _remove_flags(
        compile_flags, ["-Oz", "-Os", "-O0", "-O1", "-O2", "-O3"]
    )
    compile_flags += debug_compile_flags
    link_flags += debug_link_flags

# Optimize for RELEASE
if OPTIMIZED:
    compile_flags += ["-flto", "-Oz"]
    link_flags += ["-flto"]

if QUICK_BUILD:
    compile_flags += ["-flto=thin", "-Oz"]
    link_flags += ["-flto=thin"]

# Handle custom export name
export_name = env.GetProjectOption("custom_wasm_export_name", "")
if export_name:
    output_js = f"{BUILD_DIR}/{export_name}.js"
    link_flags += [
        f"-sMODULARIZE=1",
        f"-sEXPORT_NAME={export_name}",
        "-o",
        output_js,
    ]
    if DEBUG:
        link_flags.append("--source-map-base=http://localhost:8000/")

# Append flags to environment
env.Append(CCFLAGS=compile_flags)
env.Append(CXXFLAGS=compile_flags)
env.Append(LINKFLAGS=link_flags)


# Banner utilities
def banner(s: str) -> str:
    lines = s.split("\n")
    widest = max(len(l) for l in lines)
    border = "#" * (widest + 4)
    out = [border]
    for l in lines:
        out.append(f"# {l:<{widest}} #")
    out.append(border)
    return "\n" + "\n".join(out) + "\n"


def print_banner(msg: str) -> None:
    print(banner(msg))


# Diagnostics
print_banner("C++/C Compiler Flags:")
print("CC/CXX flags:")
for f in compile_flags:
    print(f"  {f}")
print(f"STRICT mode: {'ENABLED' if STRICT_MODE else 'DISABLED'}")

print_banner("Linker Flags:")
for f in link_flags:
    print(f"  {f}")

print_banner("End of Flags\nBegin compile/link using PlatformIO")
