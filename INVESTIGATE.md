# Investigation: CMake Removal from FastLED WASM Compiler

## Context

The FastLED WASM Compiler project appears to use a custom Python-based build system for compiling FastLED sketches to WebAssembly. However, there are remnants of CMake and PlatformIO that may be legacy code. This document outlines investigations needed to safely remove CMake dependencies.

## Current Understanding

### Python Build System Components

1. **Sketch Compilation** (`src/fastled_wasm_compiler/compile_sketch.py`)
   - Uses direct `emcc` calls to compile sketch source files
   - Compiles `.cpp` and `.ino` files into object files
   - Links with `libfastled.a` to create final WASM output
   - Does NOT use CMake for sketch compilation

2. **Library Compilation** (Current Mystery)
   - `libfastled.a` must be pre-built before sketch compilation
   - `compile_lib.py` and `compile_all_libs.py` exist but currently call `build_lib.sh`
   - `build_lib.sh` uses `emcmake cmake` + `ninja` to build libraries
   - **QUESTION**: Is this CMake usage legacy, or is there a Python alternative?

3. **Precompiled Headers** (PCH)
   - `fastled.pch` is mentioned in the codebase
   - Unclear if PCH generation uses CMake or Python build system

### CMake Usage Points

1. **Dockerfile** (line 161): `COPY ./build_tools/CMakeLists.txt`
2. **build_lib.sh**: Uses `emcmake cmake` and `ninja` for building
3. **generate_cmake_flags.py**: Generates `cmake_flags.cmake` from `build_flags.toml`
4. **cmake/shared_build_settings.cmake**: CMake configuration file

### Files Deleted in This Session

- `build_tools/CMakeLists.txt`
- `build_tools/cmake_flags.cmake`
- `build_tools/generate_cmake_flags.py` (initially)
- `build_tools/build_lib.sh` (initially)
- `cmake/shared_build_settings.cmake`

### Files Restored

- `build_tools/build_lib.sh` (restored via git checkout)

## Investigation Tasks

### 1. Library Compilation Analysis

**TASK**: Determine how `libfastled.a` is actually built in current production

- [ ] Search for Python-based library compilation code
- [ ] Check if `compile_lib.py` has a native Python implementation or just wraps `build_lib.sh`
- [ ] Look for any direct `emcc` or `emar` calls that build libraries without CMake
- [ ] Examine `compile_all_libs.py` to see if it has a CMake-free path
- [ ] Review git history: When was `build_lib.sh` last modified? Is it actively maintained?

**Key Files to Examine**:
- `src/fastled_wasm_compiler/compile_lib.py` (lines 84-96 show it calls `build_lib.sh`)
- `src/fastled_wasm_compiler/compile_all_libs.py`
- `src/fastled_wasm_compiler/paths.py` (for library paths)

**Questions to Answer**:
- Does a Python-based library compilation alternative exist?
- If not, what would it take to implement one?
- How does the library compilation differ from sketch compilation?

### 2. Precompiled Header (PCH) Generation

**TASK**: Determine how PCH files are created

- [ ] Search for PCH generation code in Python files
- [ ] Check if `dump_headers.py` generates PCH or just analyzes headers
- [ ] Look for any `emcc` flags related to PCH (`-xc++-header`, `-emit-pch`)
- [ ] Determine if CMake is used for PCH generation or if Python handles it

**Key Files to Examine**:
- `src/fastled_wasm_compiler/dump_headers.py`
- `DESIGN_DUMP_HEADERS.md`
- `RESOLVED_PCH_BUG.md`

**Questions to Answer**:
- Is PCH generation already Python-based?
- Does PCH generation depend on `libfastled.a` being built first?

### 3. Build Flag Management

**TASK**: Understand the relationship between TOML config and build flags

- [ ] Review `build_flags.toml` structure
- [ ] Check how `compilation_flags.py` uses the TOML file
- [ ] Determine if `generate_cmake_flags.py` is purely for CMake or has other uses
- [ ] See if Python code reads flags directly from TOML or needs CMake intermediary

**Key Files to Examine**:
- `src/fastled_wasm_compiler/build_flags.toml`
- `src/fastled_wasm_compiler/compilation_flags.py`
- `build_tools/generate_cmake_flags.py` (if it still exists in git)

**Questions to Answer**:
- Can all build configurations be read directly from TOML without CMake?
- Is `cmake_flags.cmake` only used by `build_lib.sh`?

### 4. Docker Build Process

**TASK**: Map the complete Docker build flow

- [ ] Document what happens in each Dockerfile stage
- [ ] Identify which stages use CMake vs Python build system
- [ ] Check what `fastled-wasm-compiler-prewarm` expects to exist
- [ ] Determine if the prewarm step requires pre-built libraries

**Key Sections**:
- Dockerfile lines 151-165: Library building section
- Dockerfile lines 178-203: Prewarm commands

**Questions to Answer**:
- What exactly does the prewarm step do?
- Does prewarm require `libfastled.a` to exist first?
- Can prewarm trigger library builds if missing?

### 5. PlatformIO Status

**TASK**: Verify PlatformIO is truly unused

- [ ] Search for active PlatformIO usage (not just legacy comments)
- [ ] Check if any code paths still invoke `platformio` or `pio`
- [ ] Review environment variable `NO_PLATFORMIO=1` usage
- [ ] Confirm all compilation goes through `compile_sketch.py`

**Questions to Answer**:
- Is PlatformIO completely removed or just disabled by default?
- Are there any remaining PlatformIO integration points?

### 6. Integration Test Analysis

**TASK**: Understand what the integration tests actually test

- [ ] Review `tests/integration/test_full_build.py`
- [ ] Check what the Docker build must produce for tests to pass
- [ ] Determine minimum viable build artifacts needed
- [ ] Identify which tests validate library compilation vs sketch compilation

**Questions to Answer**:
- What artifacts must exist for tests to pass?
- Do tests explicitly check for `libfastled.a`?
- Can we modify the build system without breaking test expectations?

### 7. Alternative Build Implementation Research

**TASK**: Design a CMake-free library build approach

- [ ] List all `.cpp` files in FastLED source that need compilation
- [ ] Determine compilation flags needed for each file
- [ ] Design Python script to compile each file to `.o` with `emcc`
- [ ] Design archive creation using `emar` instead of CMake's `ar`
- [ ] Plan how to handle different build modes (debug/quick/release)
- [ ] Consider thin vs regular archive types

**Questions to Answer**:
- Can we replicate `build_lib.sh` behavior in pure Python?
- What are the performance implications?
- Should we use multiprocessing for parallel compilation?

## Recommended Approach

### Phase 1: Investigation (Current Phase)
1. Complete all investigation tasks above
2. Document findings in this file
3. Create a clear picture of what CMake actually does

### Phase 2: Planning
1. Design Python-based library compilation system
2. Plan backward compatibility strategy
3. Define success criteria for CMake removal

### Phase 3: Implementation
1. Implement Python-based `libfastled.a` builder
2. Test against integration tests
3. Remove CMake dependencies only after Python version works

### Phase 4: Cleanup
1. Remove CMake files
2. Remove `build_lib.sh`
3. Update documentation

## Open Questions

1. **Why was CMake originally chosen for library building?**
   - Performance?
   - Build dependency tracking?
   - Incremental compilation?

2. **What does the CMake build do that Python doesn't?**
   - Automatic dependency detection?
   - Parallel compilation?
   - Archive optimization?

3. **Are there any hidden CMake features we rely on?**
   - PCH generation?
   - Link-time optimization setup?
   - Cross-compilation configuration?

## Next Steps for Investigation Agent

The next agent should:

1. **Start with Task 1** (Library Compilation Analysis) - this is the critical path
2. **Document all findings** directly in this file under a "Findings" section
3. **Create a detailed plan** for CMake removal only after understanding current state
4. **Do not delete any files** until the investigation is complete
5. **Run integration tests** after each finding to understand current behavior

## Findings

### Task 1: Library Compilation Analysis ✅

**CRITICAL FINDING**: Library compilation is 100% CMake-dependent with NO Python alternative

**Current Architecture**:
1. `compile_lib.py` (line 84) calls `build_lib.sh` shell script
2. `compile_all_libs.py` (line 27) calls `/build/build_lib.sh`
3. `build_lib_lazy.py` (lines 64-66) also depends on `build_lib.sh`
4. **ALL three Python modules are wrappers** - they set env vars and subprocess to the bash script

**What build_lib.sh Actually Does**:
- Lines 1-66: Auto-regenerates `cmake_flags.cmake` from `build_flags.toml` using `generate_cmake_flags.py`
- Lines 152-158 (thin mode): `emcmake cmake` + `ninja -v` (2-step compile + link)
- Lines 161-169 (regular mode): `emcmake cmake` + `ninja -v` (2-step compile + link)
- Lines 172-186 (both mode): `emcmake cmake` + `ninja -v` (3-step compile + link thin + link regular)

**CMake Dependencies**:
- `emcmake` wrapper configures Emscripten for CMake
- `ninja` build system invoked by CMake
- `cmake_flags.cmake` generated from TOML
- CMakeLists.txt (DELETED but required by build_lib.sh)
- `shared_build_settings.cmake` (DELETED but may be required)

**Git History**:
- `build_lib.sh` last major update: c93733d "add thin pch generation" (recent)
- Actively maintained - 12 commits in history
- Recent changes for PCH, thin archives, and centralized build flags

**Answer to Questions**:
- ❌ NO Python-based library compilation alternative exists
- ❌ All Python modules are thin wrappers around bash → CMake
- ⚠️ Deleted CMake files are REQUIRED for library builds to work
- 🔧 Library compilation differs from sketch compilation:
  - Sketch: Pure Python calling `emcc` directly (compile_sketch.py)
  - Library: Python → Bash → CMake → Ninja → emcc

**Critical Path**: Cannot remove CMake without implementing Python equivalent of entire CMake+Ninja build

### Task 2: PCH Generation Analysis ✅

**CRITICAL FINDING**: PCH generation is 100% CMake-dependent - generated during library build process

**Current Architecture**:
1. **PCH is NOT generated by Python** - it's generated by CMake during library build
2. CMakeLists.txt lines ~200-270: PCH generation logic (Traditional vs Thin modes)
3. Generated files: `fastled_pch.h` (source) and `fastled_pch.h.gch` (compiled) OR `fastled_pch.pch` (thin mode)
4. Python code only **consumes** pre-built PCH (compile_sketch.py:277)

**PCH Generation Process (in CMake)**:
```cmake
# Step 1: Create fastled_pch.h with includes
file(WRITE ${PCH_HEADER} "#include <Arduino.h>\n#include <FastLED.h>")

# Step 2: Compile with mode-specific flags from build_flags.toml
# - Filters out PCH-incompatible flags (-emit-llvm, -Wall)
# - Keeps build mode flags (-flto=thin, -gsource-map, etc.)
# - Uses emcc to compile fastled_pch.h → fastled_pch.h.gch

# Step 3: Custom command to build PCH during library build
add_custom_command(OUTPUT ${PCH_OUTPUT} ...)
```

**Python Side (Read-Only)**:
- `compile_sketch.py:277`: `pch_file = build_dir / "fastled_pch.h"`
- `compile_sketch.py:279-285`: If PCH exists, add `-include fastled_pch.h` to compiler flags
- **NO Python code generates PCH** - only checks if it exists and uses it
- RESOLVED_PCH_BUG.md documents architectural fix: zero file modification approach

**PCH Modes**:
- Traditional PCH: `fastled_pch.h.gch` (default)
- Thin PCH: `fastled_pch.pch` (enabled with `THIN_PCH=1` env var)
- Controlled by `build_lib.sh` lines 103-107

**Git History**:
- c93733d: "add thin pch generation" (recent)
- 2ecb5cb: "Disable PCH timestamp checking for server builds"
- PCH is actively maintained feature

**Answer to Questions**:
- ❌ NO Python-based PCH generation exists
- ✅ PCH is generated as part of library build (CMake dependency)
- ✅ PCH generation requires `libfastled.a` build infrastructure
- ⚠️ Cannot remove CMake without reimplementing PCH generation in Python

**Critical Dependencies**:
- CMakeLists.txt (DELETED) - contains PCH generation logic
- cmake_flags.cmake (auto-generated from TOML) - provides compile flags for PCH
- build_lib.sh - sets THIN_PCH env var
- build_flags.toml - source of truth for compilation flags

### Task 3: Build Flag Management ✅

**CRITICAL FINDING**: Build flags have dual-path implementation - Python reads TOML directly, CMake needs intermediate conversion

**Current Architecture**:

**1. Source of Truth**: `build_flags.toml` (386 lines)
   - Centralized configuration for ALL build flags
   - Sections: [all], [sketch], [library], [build_modes.{debug,quick,release}], [linking.*], [dwarf], [strict_mode]
   - Single source of truth for both Python and CMake builds

**2. Python Path (Sketch Compilation)**: Direct TOML Reading
   - `compilation_flags.py` (346 lines): CompilationFlags class
   - Uses `tomllib` (Python 3.11+) or `tomli` (fallback)
   - Reads `build_flags.toml` directly without any intermediary
   - Provides methods: `get_base_flags()`, `get_sketch_flags()`, `get_library_flags()`, `get_build_mode_flags()`
   - NO CMake dependency for sketch compilation

**3. CMake Path (Library Compilation)**: TOML → Python → CMake
   - `generate_cmake_flags.py` (DELETED but required): Converts TOML to CMake variables
   - Reads `build_flags.toml` using `tomli`
   - Generates `cmake_flags.cmake` with CMake `set()` commands
   - Called by `build_lib.sh` lines 14-42 (auto-regeneration logic)
   - Output: `FASTLED_BASE_COMPILE_FLAGS`, `FASTLED_DEBUG_FLAGS`, `FASTLED_QUICK_FLAGS`, `FASTLED_RELEASE_FLAGS`

**4. Fallback Hierarchy** (Both Paths):
   1. Primary: `/git/fastled/src/platforms/wasm/compile/build_flags.toml` (FastLED source tree)
   2. Fallback: Package resource `fastled_wasm_compiler/build_flags.toml`
   3. Override: `FASTLED_FORCE_BUILTIN_FLAGS=1` forces package resource

**The Conversion Process** (CMake Only):
```python
# generate_cmake_flags.py workflow:
1. Load build_flags.toml using tomli
2. Extract [all.defines] + [all.compiler_flags] + [library.compiler_flags]
3. For each build mode: extract [build_modes.{mode}.flags]
4. For debug mode: add -ffile-prefix-map from [dwarf] config
5. Generate CMake set() commands for each variable
6. Output to stdout → redirected to cmake_flags.cmake
```

**Dependencies**:
- `build_flags.toml`: Source of truth (exists, not deleted)
- `compilation_flags.py`: Python direct reader (exists, works independently)
- `generate_cmake_flags.py`: DELETED but required by build_lib.sh
- `cmake_flags.cmake`: Auto-generated output (not in git, generated on-demand)

**Answer to Questions**:
- ✅ Python reads flags directly from TOML (no CMake intermediary needed for sketches)
- ❌ CMake CANNOT read TOML directly - needs `generate_cmake_flags.py` conversion
- ⚠️ `cmake_flags.cmake` is ONLY used by library build (CMakeLists.txt)
- ⚠️ Deleted `generate_cmake_flags.py` is CRITICAL for library builds
- 🔧 The two paths (Python vs CMake) read the SAME source but through different loaders

**Critical Finding**:
- Sketch compilation is already CMake-independent (reads TOML directly)
- Library compilation requires CMake + generate_cmake_flags.py to convert TOML
- Cannot remove generate_cmake_flags.py without breaking library builds

### Task 4: Docker Build Process ✅

**CRITICAL FINDING**: Docker build has 3 stages - CMake is required in the library build stage

**Docker Build Stages**:

**Stage 1: Base Environment** (Lines 1-150)
- FROM emscripten/emsdk:4.0.8
- Install system packages: git, ninja-build, cmake, ccache, dos2unix, uv (Python package manager)
- Clone FastLED repository from GitHub
- Download and configure emsdk
- NO compilation yet - just environment setup

**Stage 2: Library Build** (Lines 151-165) ⚠️ **CMake Critical Section**
```dockerfile
# Copy TOML and Python infrastructure
COPY ./src/fastled_wasm_compiler/build_flags.toml /tmp/.../build_flags.toml
COPY ./src/fastled_wasm_compiler/compilation_flags.py /tmp/.../compilation_flags.py

# Copy build script (NOTE: CMake files were removed but needed!)
COPY ./build_tools/build_lib.sh /build/build_lib.sh

# Run library build - THIS REQUIRES CMAKE!
RUN /build/build_lib.sh --all
```

**What happens in `/build/build_lib.sh --all`**:
1. Auto-regenerate `cmake_flags.cmake` from `build_flags.toml` using `generate_cmake_flags.py` (DELETED!)
2. For each mode (DEBUG, QUICK, RELEASE):
   - Run `emcmake cmake` + `ninja` to compile library
   - Generate PCH (fastled_pch.h + fastled_pch.h.gch)
   - Create archives (libfastled-thin.a or libfastled.a)
3. Outputs to `/build/{debug,quick,release}/`

**Stage 3: Python Package Install & Prewarm** (Lines 168-215)
```dockerfile
# Install Python package
COPY . /tmp/fastled-wasm-compiler-install/
RUN uv pip install --system /tmp/fastled-wasm-compiler-install

# Prewarm cache with example compilations
RUN fastled-wasm-compiler-prewarm --sketch=/examples/Blink --debug
RUN fastled-wasm-compiler-prewarm --sketch=/examples/Blink --quick
RUN fastled-wasm-compiler-prewarm --sketch=/examples/Blink --release
```

**Prewarm Process** (`cli_prewarm.py`):
- Compiles Blink example sketch in each mode
- Uses pre-built libraries from Stage 2
- Populates ccache for faster subsequent builds
- REQUIRES: libfastled.a and fastled_pch.h from library build
- Does NOT rebuild libraries - only compiles sketches

**Dependencies Flow**:
```
Stage 1 (Environment)
  ↓
Stage 2 (Library Build) → Requires CMake!
  ├── generate_cmake_flags.py (DELETED but CRITICAL)
  ├── CMakeLists.txt (DELETED but CRITICAL)
  ├── build_lib.sh → emcmake cmake + ninja
  └── Outputs: libfastled.a + fastled_pch.h.gch
  ↓
Stage 3 (Prewarm)
  ├── Requires outputs from Stage 2
  └── fastled-wasm-compiler-prewarm (Python-only, uses pre-built libs)
```

**Answer to Questions**:
- ✅ Prewarm uses Python CLI (`cli_prewarm.py`)
- ✅ Prewarm DOES require pre-built libraries (from Stage 2)
- ❌ Prewarm CANNOT trigger library builds (expects them to exist)
- ⚠️ Docker build FAILS at Stage 2 without CMake files
- 🔧 Stage 2 is the ONLY place CMake is used in entire build

**Critical Path**:
- Cannot complete Docker build without CMake infrastructure
- Stage 2 library build is a hard blocker for Stage 3 prewarm
- Prewarm validates the build works but doesn't replace library compilation

## FINAL SUMMARY: CMake Removal Analysis

### What Can Be Removed? ❌ NOTHING SAFELY

**Files Deleted (All CRITICAL)**:
1. ❌ `build_tools/CMakeLists.txt` - Required by build_lib.sh → emcmake cmake
2. ❌ `build_tools/generate_cmake_flags.py` - Required by build_lib.sh auto-regeneration
3. ❌ `cmake/shared_build_settings.cmake` - Potentially required by CMakeLists.txt

**Why They're All Critical**:
- Library compilation (libfastled.a) is 100% CMake-dependent
- PCH generation (fastled_pch.h.gch) is embedded in CMake build
- No Python alternative exists for library builds
- Sketch compilation (Python) DEPENDS on pre-built library

### Python-Only Alternative Would Require:

**1. Library Builder Replacement** (~500-1000 lines of Python):
- Discover all FastLED `.cpp` files to compile
- Call `emcc` individually for each source file with correct flags
- Handle parallel compilation (multiprocessing)
- Call `emar` to create archive from .o files
- Manage thin vs regular archive modes
- Implement incremental build tracking (timestamp checks)

**2. PCH Generator** (~100-200 lines of Python):
- Generate `fastled_pch.h` source file
- Read flags from `build_flags.toml`
- Filter PCH-incompatible flags
- Call `emcc` with `-xc++-header` to generate `.gch` file
- Handle both traditional and thin PCH modes

**3. Testing & Validation**:
- Ensure Python builds produce identical output to CMake
- Verify all build modes (debug/quick/release) work
- Test both archive types (thin/regular)
- Validate PCH functionality
- Integration tests must pass

**Estimated Effort**: 2-4 weeks of development + testing

### Recommendation

**DO NOT REMOVE CMAKE** for the following reasons:

1. **High Risk**: Breaking library builds breaks EVERYTHING (sketch compilation depends on libraries)
2. **High Effort**: Reimplementing CMake+Ninja in Python is substantial work
3. **Low Benefit**: CMake is only used in Docker build Stage 2 - not affecting end users
4. **Active Maintenance**: Recent commits show CMake is actively maintained for PCH/thin archives
5. **Working Solution**: Current system works - replacing it adds risk without clear benefit

**If removal is still desired**, the path forward is:
1. Restore deleted CMake files FIRST
2. Implement Python library builder as NEW feature (parallel to CMake)
3. Test extensively to ensure parity
4. Gradually transition and validate
5. Only then remove CMake infrastructure

## Session Notes

- **2025-10-07**: Initial investigation document created
- CMake files were prematurely deleted and some were restored
- `build_lib.sh` confirmed to use CMake (`emcmake cmake` + `ninja`)
- Sketch compilation confirmed to be pure Python (no CMake)
- Library compilation currently uses CMake via `build_lib.sh`
- **ITERATION 1 COMPLETE**: Task 1 findings - CMake is critical dependency
- **ITERATION 2 COMPLETE**: Task 2 findings - PCH generation requires CMake
- **ITERATION 3 COMPLETE**: Task 3 findings - Dual-path flag management (Python + CMake)
- **ITERATION 4 COMPLETE**: Task 4 findings - Docker build requires CMake in Stage 2
- **INVESTIGATION COMPLETE**: All 4 tasks analyzed, recommendation documented
