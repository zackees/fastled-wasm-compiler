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

try:
    from fastled_wasm_compiler.compilation_flags import get_compilation_flags
    CENTRALIZED_FLAGS_AVAILABLE = True
except ImportError:
    CENTRALIZED_FLAGS_AVAILABLE = False

print("Loading wasm_compiler_flags.py")

# Determine the build environment
_IS_GITHUB = os.environ.get("GITHUB_ACTIONS", "false") == "true"

# Check if we're in Docker using the presence of platform-specific tooling
AR = os.environ.get("ENV_BUILD_TOOLS_DIR", "/build_tools") + "/emar-thin.sh"

# Wasm output format selection
USE_WASM = 1  # 0 for asm.js, 1 for WebAssembly

# ==============================================================================
# Build settings from environment
# ==============================================================================

# Linker selection
LINKER = os.environ.get("LINKER", "lld")  # Default to lld, can be set to "mold" etc

# Check for forced namespace (to prevent global namespace pollution)
FASTLED_FORCE_NAMESPACE = 1  # force all FastLED code into fl:: namespace

# Build mode from environment variable (default: QUICK)
BUILD_MODE = os.environ.get("BUILD_MODE", "QUICK").upper()
print(f"Build mode: {BUILD_MODE}")

# Strict mode from environment variable
STRICT_MODE = os.environ.get("STRICT", "").lower() in ("1", "true")
print(f"Strict mode: {STRICT_MODE}")

# Compilation flags
COMPILER_FLAGS = [
    f"-DPLATFORMIO={60118}",
    f"-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS={50}",
    f"-DFASTLED_FORCE_NAMESPACE={FASTLED_FORCE_NAMESPACE}",
    "-DFASTLED_USE_PROGMEM=0",
    "-DUSE_OFFSET_CONVERTER=0",
    "-DSKETCH_COMPILE=1",
    "-DGL_ENABLE_GET_PROC_ADDRESS=0",
    "-DIDF_CCACHE_ENABLE=1",
    "-DEMSCRIPTEN_NO_THREADS",  # Important: disable threads
    "-D_REENTRANT=0",  # Don't use reentrant code
    "-DEMSCRIPTEN_HAS_UNBOUND_TYPE_NAMES=0",  # Emscripten type name handling
]

# For drawf support it needs a file server running at this point.
# TODO: Emite this information as a src-map.json file to hold this
# port and other information.
SRC_SERVER_PORT = 8123
SRC_SERVER_HOST = f"http://localhost:{SRC_SERVER_PORT}"
SOURCE_MAP_BASE = f"--source-map-base={SRC_SERVER_HOST}"


# Determine whether to use ccache (recommended).
USE_CCACHE = True

# Get build mode from environment variable, default to QUICK if not set
valid_modes = ["DEBUG", "QUICK", "RELEASE"]
if BUILD_MODE not in valid_modes:
    raise ValueError(f"BUILD_MODE must be one of {valid_modes}, got {BUILD_MODE}")

# Check if STRICT mode is enabled (treat warnings as errors)
DEBUG = BUILD_MODE == "DEBUG"
QUICK_BUILD = BUILD_MODE == "QUICK"
OPTIMIZED = BUILD_MODE == "RELEASE"

# Choose WebAssembly (1), asm.js fallback (2)
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

# Get compilation flags from centralized configuration if available
if CENTRALIZED_FLAGS_AVAILABLE:
    try:
        flags_loader = get_compilation_flags()
        compile_flags = flags_loader.get_full_compilation_flags(
            compilation_type="library",
            build_mode=BUILD_MODE,
            fastled_src_path=FASTLED_SRC_STR,
            strict_mode=STRICT_MODE,
        )
        # Add the ERROR_ON_WASM_CHANGES_AFTER_LINK flag which is PlatformIO-specific
        compile_flags.append("-sERROR_ON_WASM_CHANGES_AFTER_LINK")
    except Exception as e:
        print(f"Warning: Failed to load centralized flags, using fallback: {e}")
        CENTRALIZED_FLAGS_AVAILABLE = False

# Fallback flags (used if centralized flags fail to load)
if not CENTRALIZED_FLAGS_AVAILABLE:
    # Base compile flags (CCFLAGS/CXXFLAGS) - FALLBACK
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
        "-DEMSCRIPTEN_HAS_UNBOUND_TYPE_NAMES=0",  # Emscripten type name handling
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
    f"-fuse-ld={LINKER}",  # Configurable linker (lld, mold, etc.)
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

# Archive selection based on volume mapped source availability
def get_fastled_library_path(build_mode_lower):
    """Get the FastLED library path based on volume mapped source availability."""
    build_root = os.environ.get("ENV_BUILD_ROOT", "/build")
    thin_lib = f"{build_root}/{build_mode_lower}/libfastled-thin.a"
    regular_lib = f"{build_root}/{build_mode_lower}/libfastled.a"
    
    # Check if volume mapped source is defined
    is_volume_mapped = os.environ.get("ENV_VOLUME_MAPPED_SRC") is not None
    
    if is_volume_mapped:
        # Volume mapped source is defined, respect NO_THIN_LTO flag
        no_thin_lto = os.environ.get("NO_THIN_LTO", "0") == "1"
        if no_thin_lto:
            print(f"Volume mapped source defined, NO_THIN_LTO=1: Using regular FastLED library: {regular_lib}")
            return regular_lib
        else:
            print(f"Volume mapped source defined, NO_THIN_LTO=0: Using thin FastLED library: {thin_lib}")
            return thin_lib
    else:
        # Volume mapped source not defined, always use regular archives
        print(f"Volume mapped source not defined: Using regular FastLED library: {regular_lib}")
        return regular_lib

# Get the appropriate library path based on build mode
build_mode_lower = BUILD_MODE.lower()
fastled_lib_path = get_fastled_library_path(build_mode_lower)

# Note: Library linking is handled by platformio.ini, not here
print(f"FastLED library will be: {fastled_lib_path}")

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
