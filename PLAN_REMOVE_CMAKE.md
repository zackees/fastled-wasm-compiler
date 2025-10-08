# Plan: Remove CMake Dependency from fastled-wasm-compiler

## Executive Summary

FastLED's main repository (`~/dev/fastled`) has a **Python-native build system** in `ci/compiler/` that compiles libraries and generates PCH files **without CMake**. This plan outlines how to adopt that approach in `fastled-wasm-compiler`.

---

## Discovery: FastLED's Native Build System

### Location
- **Path**: `~/dev/fastled/ci/compiler/`
- **Key Files**:
  - `clang_compiler.py` - Core compiler/archiver/linker implementation
  - `build_dynamic_lib.py` - Example of building libfastled.so without CMake
  - `build_unit.toml` - Build configuration (similar to fastled-wasm-compiler's build_flags.toml)

### Architecture

FastLED uses a **pure Python build system** that:

1. **Reads TOML configuration** (`build_unit.toml`)
2. **Compiles C++ files** directly with `clang++` or `python -m ziglang c++`
3. **Generates PCH** by calling compiler with `-x c++-header`
4. **Creates archives** by calling `ar` command
5. **Links programs** by calling linker directly

**NO CMAKE OR NINJA** - Everything is direct subprocess calls to compilers/tools.

---

## Current State: fastled-wasm-compiler Dependencies

### What We Currently Have (CMake-based):

```
Python Entry Points
    ↓
    subprocess → build_lib.sh (bash)
        ↓
        emcmake cmake + ninja
            ↓
            CMakeLists.txt
                ↓
                Calls emcc/emar
```

### What FastLED Has (Python-native):

```
Python Entry Points
    ↓
    Compiler class (clang_compiler.py)
        ↓
        Direct subprocess calls to emcc/emar
```

---

## FastLED's Build System Components

### 1. **Compiler Class** (`clang_compiler.py`)

**Key Features**:
- `Compiler` class wraps compilation/archiving/linking operations
- Uses `ThreadPoolExecutor` for parallel compilation
- Fingerprint-based caching for incremental builds
- Direct compiler invocation (no CMake)

**Core Methods**:

#### a) **compile_cpp_file()** - Compiles single C++ file
```python
def compile_cpp_file(
    self,
    source_file: Path,
    output_path: Path,
    additional_flags: list[str] = []
) -> Future[Result]:
    # Build command from TOML configuration
    cmd = self.settings.compiler.split()  # e.g., ["emcc"]
    cmd.extend(self.settings.compiler_args)
    cmd.extend(self.build_flags.compiler_flags)
    cmd.extend(self.build_flags.defines)
    cmd.extend(["-c", str(source_file), "-o", str(output_path)])

    # Submit to thread pool
    return _EXECUTOR.submit(subprocess.run, cmd, ...)
```

#### b) **generate_pch()** - Creates precompiled header
```python
def generate_pch(self) -> bool:
    # Create header file content
    pch_content = self.generate_pch_header()  # Default or custom

    # Write to temporary file
    pch_header_path = Path(tempfile.mktemp(suffix=".hpp"))
    pch_header_path.write_text(pch_content)

    # Compile PCH with compiler
    cmd = self.settings.compiler.split()
    cmd.extend([
        "-x", "c++-header",  # Treat as header file
        f"-I{self.settings.include_path}",
        "-D...defines...",
        str(pch_header_path),
        "-o", str(pch_output_path)
    ])

    subprocess.run(cmd, ...)
    self._pch_file_path = pch_output_path
    self._pch_ready = True
```

**PCH Usage**:
- Lines 680-681: Adds `-include-pch <path>` to compiler commands
- Fingerprint caching determines if PCH needs rebuild
- PCH contains common includes (Arduino.h, FastLED.h, etc.)

#### c) **create_archive()** - Creates .a static library
```python
def create_archive_sync(
    object_files: list[Path],
    output_archive: Path,
    options: LibarchiveOptions,
    archiver: str,  # From TOML config
    build_flags_config: BuildFlags
) -> Result:
    # Get archive flags from TOML [archive] section
    archive_flags = build_flags_config.archive.flags  # e.g., "rcsD"

    # Build ar command
    cmd = [archiver, archive_flags, str(output_archive)]
    cmd.extend([str(obj) for obj in object_files])

    # Execute ar command
    result = subprocess.run(cmd, ...)
    return Result(ok=result.returncode == 0, ...)
```

**Archive Options**:
- Supports thin archives (`-T` flag)
- Platform-specific flags from TOML
- Uses `ar` directly (or `emar` for Emscripten)

---

### 2. **BuildFlags Class** - TOML Configuration Parser

**Location**: `clang_compiler.py` lines 224-450

**Structure**:
```python
@dataclass
class BuildFlags:
    defines: List[str]
    compiler_flags: List[str]
    include_flags: List[str]
    link_flags: List[str]
    strict_mode_flags: List[str]
    tools: BuildTools
    archive: ArchiveOptions

    @classmethod
    def parse(cls, toml_path: Path, quick_build: bool, strict_mode: bool):
        config = tomllib.load(toml_path)

        # Extract tools from [tools] section
        tools = BuildTools(
            cpp_compiler=config["tools"]["cpp_compiler"],
            archiver=config["tools"]["archiver"],
            linker=config["tools"]["linker"],
            ...
        )

        # Extract archive options from [archive] section
        archive = ArchiveOptions(
            flags=config["archive"]["flags"],  # e.g., "rcsD"
            ...
        )

        # Combine flags based on build mode
        if quick_build:
            flags = config["quick"]["flags"]
        else:
            flags = config["debug"]["flags"]

        return BuildFlags(...)
```

**TOML Structure** (build_unit.toml):
```toml
[tools]
cpp_compiler = ["uv", "run", "python", "-m", "ziglang", "c++"]
archiver = ["ar"]
linker = ["clang++"]
c_compiler = ["clang"]
objcopy = ["objcopy"]
nm = ["nm"]
strip = ["strip"]
ranlib = ["ranlib"]

[archive]
flags = "rcsD"  # r=insert, c=create, s=index, D=deterministic

[all]
defines = ["-DFASTLED_FORCE_NAMESPACE=1", ...]
compiler_flags = ["-std=c++17", "-fPIC", ...]

[debug]
flags = ["-g3", "-O0", ...]

[quick]
flags = ["-O1", "-g0", ...]
```

---

### 3. **build_dynamic_lib.py** - Complete Example

**Workflow** (lines 22-196):
```python
def build_fastled_dynamic_library(build_dir: Path) -> Path:
    # 1. Create compiler instance
    settings = CompilerOptions(
        include_path=PROJECT_ROOT / "src",
        defines=["STUB_PLATFORM", "ARDUINO=10808", ...],
        compiler="clang++",
        compiler_args=["-I...", "-shared", "-fPIC"],
        use_pch=True,
        parallel=True
    )

    build_flags = BuildFlags.parse(
        Path(PROJECT_ROOT) / "ci" / "build_unit.toml",
        quick_build=False,
        strict_mode=True
    )

    compiler = Compiler(settings, build_flags)

    # 2. Find all source files
    fastled_src_dir = PROJECT_ROOT / "src"
    all_cpp_files = list(fastled_src_dir.rglob("*.cpp"))

    # 3. Compile to object files
    object_files = []
    for src_file in all_cpp_files:
        obj_path = build_dir / f"{src_file.stem}.o"
        future = compiler.compile_cpp_file(
            src_file,
            output_path=obj_path,
            additional_flags=["-c", "-fPIC", ...]
        )
        result = future.result()
        object_files.append(obj_path)

    # 4. Link library (or create archive for static)
    link_cmd = ["clang++", "-shared", "-o", "libfastled.so"]
    link_cmd.extend([str(obj) for obj in object_files])
    subprocess.run(link_cmd)
```

**Key Points**:
- **Lines 75-77**: Discovers all .cpp files with `rglob("*.cpp")`
- **Lines 88-110**: Compiles each file with `compiler.compile_cpp_file()`
- **Lines 112-138**: Links with direct subprocess call
- **No CMake, no Ninja, no build scripts**

---

## Migration Plan

### Phase 1: Adopt FastLED's Compiler Infrastructure

#### Step 1.1: Copy Core Compiler Files
**Action**: Copy FastLED's compiler infrastructure to fastled-wasm-compiler

**Files to copy**:
```bash
# Source
~/dev/fastled/ci/compiler/clang_compiler.py
~/dev/fastled/ci/fingerprint_cache.py  # Dependency

# Destination
src/fastled_wasm_compiler/native_compiler.py
src/fastled_wasm_compiler/fingerprint_cache.py
```

**Modifications needed**:
- Replace `ziglang` with `emcc`/`em++` for WASM compilation
- Keep TOML parsing structure (already compatible)
- Adapt include paths for Emscripten environment

#### Step 1.2: Extend build_flags.toml with [tools] and [archive] sections

**Current**: `src/fastled_wasm_compiler/build_flags.toml`
**Missing**: `[tools]` and `[archive]` sections

**Add to build_flags.toml**:
```toml
[tools]
cpp_compiler = ["emcc"]  # or ["em++"]
c_compiler = ["emcc"]
archiver = ["emar"]  # Emscripten's ar
linker = ["emcc"]
objcopy = ["llvm-objcopy"]  # Emscripten provides this
nm = ["llvm-nm"]
strip = ["llvm-strip"]
ranlib = ["emranlib"]

[archive]
flags = "rcsD"  # Standard ar flags

[archive.emscripten]
# Emscripten-specific archive flags
flags = "rcs"  # May need to omit 'D' for WASM

[thin_archive]
# For thin archive support
flags = "rcsT"  # T = thin archive
```

---

### Phase 2: Implement Native Library Builder

#### Step 2.1: Create native_compile_lib.py

**File**: `src/fastled_wasm_compiler/native_compile_lib.py`

**Implementation**:
```python
#!/usr/bin/env python3
"""
Native library compiler for FastLED WASM.
Replaces CMake-based build_lib.sh with pure Python implementation.
"""

from pathlib import Path
from typing import List
from concurrent.futures import Future

from .native_compiler import Compiler, CompilerOptions, BuildFlags, LibarchiveOptions
from .compilation_flags import get_compilation_flags
from .paths import BUILD_ROOT, get_fastled_source_path
from .types import BuildMode


class NativeLibraryBuilder:
    """Builds libfastled.a using native Python compiler (no CMake)."""

    def __init__(self, build_mode: BuildMode, use_thin_archive: bool = False):
        self.build_mode = build_mode
        self.use_thin_archive = use_thin_archive
        self.build_dir = BUILD_ROOT / build_mode.name.lower()
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Load build flags from TOML
        flags_loader = get_compilation_flags()

        # Create compiler settings
        self.settings = CompilerOptions(
            include_path=get_fastled_source_path(),
            compiler="emcc",
            defines=self._extract_defines(flags_loader),
            std_version="gnu++17",
            compiler_args=self._get_compiler_args(flags_loader),
            use_pch=True,
            pch_header_content=self._generate_pch_content(),
            pch_output_path=str(self.build_dir / "fastled_pch.h.gch"),
            archiver="emar",
            archiver_args=[],
            parallel=True
        )

        # Load build flags
        # Note: Will need to adapt BuildFlags.parse() to work with our TOML structure
        # OR convert our build_flags.toml to match FastLED's format

        self.compiler = Compiler(self.settings, build_flags)

    def _extract_defines(self, flags_loader) -> List[str]:
        """Extract defines from compilation_flags.py format."""
        base_flags = flags_loader.get_base_flags()
        library_flags = flags_loader.get_library_flags()
        mode_flags = flags_loader.get_build_mode_flags(self.build_mode.name.lower())

        # Combine and filter for -D flags
        all_flags = base_flags + library_flags + mode_flags
        return [flag[2:] for flag in all_flags if flag.startswith("-D")]

    def _get_compiler_args(self, flags_loader) -> List[str]:
        """Get non-define compiler flags."""
        all_flags = flags_loader.get_full_compilation_flags(
            compilation_type="library",
            build_mode=self.build_mode.name.lower(),
            fastled_src_path=get_fastled_source_path()
        )
        # Filter out defines (handled separately)
        return [flag for flag in all_flags if not flag.startswith("-D")]

    def _generate_pch_content(self) -> str:
        """Generate PCH header content for WASM."""
        return """// FastLED WASM PCH - Precompiled header for faster compilation
#pragma once

// Core Arduino compatibility
#include <Arduino.h>

// FastLED main header
#include <FastLED.h>

// Common standard library headers
#include <stdint.h>
#include <stdlib.h>
"""

    def build(self) -> Path:
        """Build libfastled.a and return path to archive."""
        print(f"🔨 Building FastLED library ({self.build_mode.name} mode)")

        # 1. Find all FastLED source files
        fastled_src = Path(get_fastled_source_path())
        all_cpp_files = list(fastled_src.rglob("*.cpp"))

        # Filter out platform-specific files (keep only WASM and shared)
        wasm_cpp_files = [
            f for f in all_cpp_files
            if "platforms/wasm" in str(f) or "platforms" not in str(f)
        ]

        print(f"📂 Found {len(wasm_cpp_files)} source files to compile")

        # 2. Compile all source files to object files
        object_files: List[Path] = []
        futures: List[Future] = []

        for src_file in wasm_cpp_files:
            # Create object file path
            relative_path = src_file.relative_to(fastled_src)
            safe_name = str(relative_path.with_suffix("")).replace("/", "_").replace("\\", "_")
            obj_path = self.build_dir / f"{safe_name}.o"

            # Submit compilation
            future = self.compiler.compile_cpp_file(
                src_file,
                output_path=obj_path,
                additional_flags=["-c"]  # Compile only, don't link
            )
            futures.append((future, obj_path, src_file))

        # Wait for all compilations
        for future, obj_path, src_file in futures:
            result = future.result()
            if not result.ok:
                raise RuntimeError(f"Failed to compile {src_file}:\n{result.stderr}")
            object_files.append(obj_path)

        print(f"✅ Compiled {len(object_files)} object files")

        # 3. Create static library archive
        archive_name = "libfastled-thin.a" if self.use_thin_archive else "libfastled.a"
        output_archive = self.build_dir / archive_name

        archive_options = LibarchiveOptions(use_thin=self.use_thin_archive)

        print(f"📦 Creating archive: {archive_name}")
        archive_future = self.compiler.create_archive(
            object_files,
            output_archive,
            archive_options
        )

        result = archive_future.result()
        if not result.ok:
            raise RuntimeError(f"Failed to create archive:\n{result.stderr}")

        print(f"✅ Library built successfully: {output_archive}")
        return output_archive


def build_library(
    build_mode: BuildMode,
    use_thin_archive: bool = False
) -> Path:
    """
    Build FastLED library for WASM using native Python compiler.

    Args:
        build_mode: Debug, Quick, or Release
        use_thin_archive: Create thin archive for faster linking

    Returns:
        Path to built library archive
    """
    builder = NativeLibraryBuilder(build_mode, use_thin_archive)
    return builder.build()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build FastLED WASM library")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--quick", action="store_true", help="Quick mode")
    parser.add_argument("--release", action="store_true", help="Release mode")
    parser.add_argument("--thin", action="store_true", help="Create thin archive")

    args = parser.parse_args()

    if args.debug:
        mode = BuildMode.DEBUG
    elif args.quick:
        mode = BuildMode.QUICK
    elif args.release:
        mode = BuildMode.RELEASE
    else:
        mode = BuildMode.QUICK

    build_library(mode, use_thin_archive=args.thin)
```

**Key Features**:
- Uses `Compiler` class from FastLED's infrastructure
- Discovers FastLED source files with `rglob("*.cpp")`
- Compiles in parallel using thread pool
- Creates archive with `emar`
- Generates PCH using compiler's `generate_pch()` method

---

### Phase 3: Replace CMake Callers

#### Step 3.1: Update compile_lib.py

**Current** (line 84):
```python
cmd = f"build_lib.sh --{build_mode.name}"
rtn = subprocess.call(cmd, shell=True, cwd=cwd, env=env)
```

**New**:
```python
from .native_compile_lib import build_library

archive_path = build_library(
    build_mode=build_mode,
    use_thin_archive=True  # Based on env var
)
return 0 if archive_path.exists() else 1
```

#### Step 3.2: Update compile_all_libs.py

**Current** (line 54):
```python
cmd = _get_cmd(build_mode)
result = subprocess.run(cmd, env=env_thin, ...)
```

**New**:
```python
from .native_compile_lib import build_library

for build_mode in ["debug", "quick", "release"]:
    archive_path = build_library(
        build_mode=BuildMode[build_mode.upper()],
        use_thin_archive=(archive_type != ArchiveType.REGULAR)
    )
```

#### Step 3.3: Update build_lib_lazy.py

**Current** (line 80):
```python
subprocess.run(
    ["bash", str(build_script), f"--{build_mode_lower}"],
    ...
)
```

**New**:
```python
from .native_compile_lib import build_library

if self._should_rebuild():
    build_library(
        build_mode=BuildMode[build_mode.upper()],
        use_thin_archive=True
    )
```

---

### Phase 4: Testing and Validation

#### Step 4.1: Unit Tests
**File**: `tests/unit/test_native_compile_lib.py`

```python
def test_native_library_builder_quick_mode():
    """Test building library in quick mode."""
    builder = NativeLibraryBuilder(BuildMode.QUICK, use_thin_archive=False)
    archive = builder.build()

    assert archive.exists()
    assert archive.name == "libfastled.a"
    assert archive.stat().st_size > 0

def test_native_library_builder_thin_archive():
    """Test building thin archive."""
    builder = NativeLibraryBuilder(BuildMode.QUICK, use_thin_archive=True)
    archive = builder.build()

    assert archive.exists()
    assert archive.name == "libfastled-thin.a"
    # Thin archives should be smaller
    assert archive.stat().st_size < 10000  # Thin archives are tiny

def test_pch_generation():
    """Test PCH is generated correctly."""
    builder = NativeLibraryBuilder(BuildMode.DEBUG)
    # PCH generation happens during compiler init
    pch_path = builder.build_dir / "fastled_pch.h.gch"

    # Trigger PCH generation
    builder.compiler.generate_pch()

    assert pch_path.exists()
    assert pch_path.stat().st_size > 0
```

#### Step 4.2: Integration Tests
**Modify**: `tests/integration/test_full_build.py`

```python
def test_native_library_build_quick():
    """Test native library build produces same output as CMake."""
    from fastled_wasm_compiler.native_compile_lib import build_library

    archive = build_library(BuildMode.QUICK, use_thin_archive=False)

    assert archive.exists()
    # Test that sketch compilation works with native library
    # (existing integration tests validate sketch compilation)
```

#### Step 4.3: Binary Compatibility Check

**Compare outputs**:
```bash
# Build with CMake
./build_lib.sh --quick

# Build with Python
python -m fastled_wasm_compiler.native_compile_lib --quick

# Compare archives (should have same symbols)
nm /build/quick/libfastled.a > cmake_symbols.txt
nm /build/quick/libfastled_native.a > native_symbols.txt
diff cmake_symbols.txt native_symbols.txt
```

---

### Phase 5: Dockerfile Migration

#### Step 5.1: Update Dockerfile Stage 2

**Current** (lines 151-165):
```dockerfile
# Copy build script (CMake files removed)
COPY ./build_tools/build_lib.sh /build/build_lib.sh

RUN chmod +x /build/build_lib.sh && \
    dos2unix /build/build_lib.sh
RUN /build/build_lib.sh --all
```

**New**:
```dockerfile
# Install Python package FIRST (needed for native compiler)
COPY . /tmp/fastled-wasm-compiler-install/
RUN uv pip install --system /tmp/fastled-wasm-compiler-install

# Build libraries using native Python compiler
RUN python -m fastled_wasm_compiler.native_compile_lib --debug
RUN python -m fastled_wasm_compiler.native_compile_lib --quick
RUN python -m fastled_wasm_compiler.native_compile_lib --release
```

**Benefits**:
- No bash scripts
- No CMake/Ninja dependencies
- All Python, consistent with rest of compiler

---

## Implementation Checklist

### ✅ Phase 1: Infrastructure
- [ ] Copy `clang_compiler.py` → `native_compiler.py`
- [ ] Copy `fingerprint_cache.py`
- [ ] Adapt for Emscripten (replace ziglang with emcc)
- [ ] Add `[tools]` and `[archive]` sections to `build_flags.toml`
- [ ] Test BuildFlags.parse() with updated TOML

### ✅ Phase 2: Native Builder
- [ ] Implement `native_compile_lib.py`
- [ ] Implement `NativeLibraryBuilder` class
- [ ] Test source file discovery
- [ ] Test parallel compilation
- [ ] Test archive creation
- [ ] Test PCH generation

### ✅ Phase 3: Integration
- [ ] Update `compile_lib.py` to call native builder
- [ ] Update `compile_all_libs.py` to call native builder
- [ ] Update `build_lib_lazy.py` to call native builder
- [ ] Ensure backward compatibility during transition

### ✅ Phase 4: Testing
- [ ] Write unit tests for NativeLibraryBuilder
- [ ] Update integration tests
- [ ] Binary compatibility verification
- [ ] Performance benchmarking (native vs CMake)

### ✅ Phase 5: Docker
- [ ] Update Dockerfile to use native builder
- [ ] Remove CMake/Ninja from dependencies
- [ ] Test Docker build end-to-end
- [ ] Verify prewarm step still works

### ✅ Phase 6: Cleanup
- [ ] Remove `build_lib.sh`
- [ ] Remove CMake requirement from Dockerfile apt-get
- [ ] Remove Ninja requirement
- [ ] Update documentation
- [ ] Remove `build_tools/CMakeLists.txt` (already deleted)
- [ ] Remove `build_tools/generate_cmake_flags.py` (already deleted)
- [ ] Remove `cmake/shared_build_settings.cmake` (already deleted)

---

## Expected Outcomes

### Performance
- **Faster compilation**: No CMake configuration overhead
- **Better caching**: Fingerprint-based incremental builds
- **Parallel compilation**: Python ThreadPoolExecutor

### Maintainability
- **Single language**: All build logic in Python
- **Shared code**: Same compiler infrastructure as FastLED main repo
- **TOML-driven**: Easy configuration changes

### Dependencies Removed
- ❌ CMake (3.10+)
- ❌ Ninja
- ❌ bash (build_lib.sh)
- ❌ emcmake wrapper

### Dependencies Added
- ✅ None! (All pure Python stdlib + existing deps)

---

## Risk Mitigation

### Risk 1: Different Build Output
**Mitigation**: Binary compatibility tests comparing CMake vs Python builds

### Risk 2: Missing Edge Cases
**Mitigation**: Keep CMake build path as fallback during transition (env var `USE_CMAKE_BUILD=1`)

### Risk 3: Performance Regression
**Mitigation**: Benchmark both approaches, profile bottlenecks

### Risk 4: PCH Incompatibility
**Mitigation**: Use exact same compiler flags, test PCH with integration tests

---

## Timeline Estimate

- **Phase 1**: 2-3 days (Infrastructure setup)
- **Phase 2**: 3-5 days (Native builder implementation)
- **Phase 3**: 1-2 days (Integration)
- **Phase 4**: 2-3 days (Testing)
- **Phase 5**: 1 day (Docker updates)
- **Phase 6**: 1 day (Cleanup)

**Total**: 10-15 days

---

## Success Criteria

1. ✅ `./test` passes (all unit and integration tests)
2. ✅ `./lint` passes (code quality maintained)
3. ✅ Docker build succeeds without CMake
4. ✅ Sketch compilation works with Python-built libraries
5. ✅ Binary output identical to CMake build (verified with `nm`)
6. ✅ Build time <= CMake approach (or faster)
7. ✅ Documentation updated

---

## Conclusion

FastLED's native Python build system provides a **proven, production-ready alternative** to CMake. By adopting this approach, we can:

- ✅ Remove CMake dependency entirely
- ✅ Simplify build system (single language)
- ✅ Share code with FastLED main repository
- ✅ Improve maintainability and debugging

The migration is **low-risk** with **high reward** - FastLED has already validated this approach for compiling the exact same library we're trying to build.

**Recommendation**: Proceed with implementation.
