# FastLED WASM Compiler

A Python-based build system that compiles FastLED C++ sketches to WebAssembly (WASM) for running Arduino/FastLED projects in web browsers using the Emscripten toolchain.

[![Linting](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml)

[![Win_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml)
[![Ubuntu_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml)
[![MacOS_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml)

[![Build and Push Multi Docker Image](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml)



```bash
# Option 1: Clone only main branch
git clone -b main --single-branch https://github.com/zackees/fastled-wasm-compiler.git

# Option 2: Clone normally then configure to exclude gh-pages
git clone https://github.com/zackees/fastled-wasm-compiler.git
cd fastled-wasm-compiler
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/* ^refs/heads/gh-pages"
```

## Features

### Core Compilation Pipeline
- **Cross-Platform Support**: Compile FastLED C++ sketches to WASM for browser execution
- **Multiple Build Modes**: Debug, quick, release, and fast-debug modes with different optimization levels
- **Thread-Safe Compilation**: Uses fasteners ReaderWriterLock for concurrent build operations
- **Smart Caching**: Integrates ccache for faster rebuild times

### Build System Architecture
- **Emscripten Integration**: Uses Emscripten SDK for WebAssembly compilation
- **Source Synchronization**: Automatically syncs FastLED source code from volume-mapped directories
- **Arduino Compatibility**: Converts .ino files to C++ and provides Arduino.h compatibility layer
- **Library Management**: Compiles FastLED libraries separately for optimized builds
- **Asset Management**: Copies web assets (index.html, index.js) and generates manifests

### Command Line Tools
- `fastled-wasm-compiler`: Main compilation tool with multiple build modes
- `fastled-wasm-compiler-prewarm`: Pre-warms compiler cache for faster builds
- `fastled-wasm-compiler-native`: Native compilation support
- `fastled-wasm-compiler-printenv`: Environment diagnostics
- `fastled-wasm-compiler-symbol-resolution`: Symbol resolution utilities
- `fastled-wasm-compiler-build-lib-lazy`: Lazy library building

### Advanced Features
- **Persistent Session Builds**: Session-based compilation with incremental build caching
- **Time-Based Lease Management**: Lock-free concurrency with automatic session cleanup
- **Thin Archives**: Support for thin archive format for better cacheability
- **Precompiled Headers**: Optimized compilation with PCH support
- **Header Dumping**: Extract and dump header files with `--headers` flag
- **Strict Mode**: Treat compiler warnings as errors with `--strict`
- **Build Profiling**: Performance profiling of the build system
- **Docker Support**: Complete containerized build environment

## Development

Run `./install` to install the dependencies.

Run `./lint` to run the linter.

Run `./test` to run the tests.

## Usage

### Basic Compilation
```bash
# Compile with default settings (all build modes)
fastled-wasm-compiler

# Compile specific build mode
fastled-wasm-compiler --release

# Compile with custom paths
fastled-wasm-compiler --compiler-root /path/to/sketch --mapped-dir /path/to/source
```

### Build Modes
- **Debug**: Full debugging symbols, sanitizers, no optimization (`-g3 -O0 -fsanitize=address,undefined`)
- **Quick**: Default fast build mode for development
- **Release**: Optimized production build
- **Fast Debug**: Faster iteration debugging mode

### Advanced Options
```bash
# Clear compiler cache
fastled-wasm-compiler --clear-ccache

# Strict mode (warnings as errors)
fastled-wasm-compiler --strict

# Dump headers to directory
fastled-wasm-compiler --headers ./output/headers

# Profile build performance
fastled-wasm-compiler --profile
```

## Build System Architecture

### Core Components
- **Compiler Pipeline** (`src/fastled_wasm_compiler/compiler.py`): Main compilation orchestration
- **Session Directory Manager** (`src/fastled_wasm_compiler/session_directory_manager.py`): Persistent session-based builds
- **Source Processing** (`process_ino_files.py`, `transform_to_cpp.py`): Arduino .ino to C++ conversion
- **Library Compilation** (`compile_all_libs.py`, `compile_lib.py`): FastLED library building
- **Asset Management** (`copy_files_and_output_manifest.py`): Web asset handling

### Build Process
1. **Source Sync**: Updates FastLED source from volume-mapped directories
2. **File Processing**: Converts .ino files to C++ with Arduino compatibility
3. **Library Compilation**: Builds FastLED libraries for target platform
4. **Sketch Compilation**: Compiles user sketch with Emscripten
5. **Asset Deployment**: Copies web assets and generates manifest

## Persistent Session Builds

The compiler supports persistent, session-based build directories that enable incremental compilation and faster rebuild times.

### Key Features
- **Incremental Builds**: Reuses build artifacts (object files, PCH caches) across compilations
- **Session Isolation**: Each user session gets isolated `/sketch/session-{id}/` directory
- **Time-Based Leases**: Lock-free concurrency using time-based safety windows (20 min worker lease, 40 min GC grace period)
- **Automatic Cleanup**: Background garbage collection removes stale sessions after 40 minutes
- **Performance**: 2-10x faster incremental builds with warm ccache

### Session Directory Structure
```
/sketch/
└── session-{id}/
    ├── src/           # Source files
    ├── debug/         # Debug build artifacts
    ├── quick/         # Quick build artifacts (default)
    ├── release/       # Release build artifacts
    └── fast_debug/    # Fast debug build artifacts
```

### Configuration
```bash
# Environment variables
ENV_SKETCH_BUILD_ROOT="/sketch"       # Session directory root
ENV_WORKER_LEASE_DURATION="1200"     # 20 minutes (worker lease)
ENV_GC_GRACE_PERIOD="2400"           # 40 minutes (GC grace period)
```

### Usage with Session ID
The compiler accepts an optional `--session-id` parameter for persistent builds:
```bash
# First compilation (creates session directory)
fastled-wasm-compiler --session-id 12345678901234567890

# Subsequent compilation (reuses build artifacts)
fastled-wasm-compiler --session-id 12345678901234567890
```

When used with the server (`fastled-wasm-server`), session IDs are managed automatically via HTTP headers. See `src/fastled_wasm_compiler/session_directory_manager.py` for complete architecture details including concurrency analysis and API integration.

## Thin Archives & Precompiled Headers

The FastLED WASM compiler supports advanced build optimizations:

### Thin Archives
Optimized archive format for better cacheability and faster linking.

### Precompiled Headers (PCH)
Accelerated compilation through precompiled headers.

To enable optimizations:
```bash
# Environment variables
THIN_PCH=1 ./build_tools/build_lib.sh --all

# Command line flags
./build_tools/build_lib.sh --thin-pch --all
```

## Docker Support

Complete containerized development environment:

```bash
# Build and run with Docker Compose
docker-compose up

# Interactive development
./run_interactive.sh
```

**Container Features:**
- Emscripten SDK pre-installed
- All build dependencies configured
- Volume mapping for source code
- Cross-platform support (x64, ARM64)

## Testing

### Unit Tests
```bash
# Run all tests
./test

# Unit tests only
uv run pytest tests/unit -v

# Integration tests only
uv run pytest tests/integration -v -s
```

### Test Structure
- `tests/unit/`: Component-specific tests
- `tests/integration/`: Full compilation pipeline tests
- Test data in `test_data/` with mock environments

## Environment Requirements

- **Python**: 3.10+
- **Emscripten SDK**: For WASM compilation
- **ccache**: For build acceleration
- **Docker**: For containerized builds (optional)

## Key Dependencies

- `fasteners==0.19`: Thread-safe file locking
- `httpx>=0.28.1`: HTTP client for downloads
- `black>=25.1.0`: Code formatting
- `pytest`: Testing framework

# Notes:
