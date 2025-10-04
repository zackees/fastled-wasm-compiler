# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastLED WASM Compiler is a Python-based build system that compiles FastLED C++ code to WebAssembly (WASM). The system uses Emscripten toolchain and PlatformIO to cross-compile Arduino/FastLED sketches for web browsers.

## Development Commands

### Setup and Installation
- `./install` - Install dependencies using uv (creates virtual environment, installs package and testing requirements)
- `source activate` - Activate the virtual environment (symlinked to `.venv/bin/activate` or `.venv/Scripts/activate` on Windows)

### Testing
- `./test` - Run all tests (unit tests with pytest -n auto, then integration tests sequentially)
- `uv run pytest tests/unit -v` - Run unit tests only
- `uv run pytest tests/integration -v -s` - Run integration tests only

### Linting and Code Quality
- `./lint` - Run complete linting pipeline (ruff, black, isort, pyright)
- `uv run ruff check --fix src` - Fix code style issues
- `uv run black src tests` - Format code with black
- `uv run pyright src tests` - Type checking

### Build and Compilation
- `fastled-wasm-compiler` - Main CLI entry point for compiling FastLED sketches
- `fastled-wasm-compiler-prewarm` - Prewarm the compiler cache

## Architecture

### Core Components

**Compiler Pipeline (`src/fastled_wasm_compiler/`)**:
- `compiler.py` - Main Compiler class with thread-safe compilation using fasteners ReaderWriterLock
- `run_compile.py` - Core compilation orchestration logic
- `args.py` - Dataclass-based argument parsing with build modes (debug/quick/release)
- `cli.py` - Command-line interface with simplified argument layer

**Build Process**:
1. Source synchronization (`sync.py`) - Updates FastLED source from volume-mapped directories
2. File processing (`process_ino_files.py`, `transform_to_cpp.py`) - Converts Arduino .ino files to C++
3. Library compilation (`compile_all_libs.py`, `compile_lib.py`) - Compiles FastLED libraries
4. Sketch compilation (`compile_sketch.py`) - Compiles user sketch code
5. Asset copying (`copy_files_and_output_manifest.py`) - Copies web assets and generates manifest

### Build Modes
- **Debug**: Full debugging symbols, sanitizers, no optimization (`-g3 -O0 -fsanitize=address,undefined`)
- **Quick**: Default fast build mode (default when no mode specified)
- **Release**: Optimized production build

### Key Paths
- `SKETCH_ROOT` - Default compiler root directory
- `FASTLED_SRC` - FastLED library source location
- `VOLUME_MAPPED_SRC` - Docker volume-mapped source directory
- Assets directory: `platforms/wasm/compiler` (contains index.html, index.js, modules/)

### Testing Structure
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Full compilation pipeline tests
- Test data in `test_data/` directories with mock compiler environments

## Docker Integration

The project includes Docker support:
- `Dockerfile` - Main container definition
- `docker-compose.yml` - Development environment setup
- `run_interactive.sh` - Interactive Docker development script
- `entrypoint.sh` - Container entry point

## Package Configuration

- `pyproject.toml` - Main package configuration with dependencies (platformio==6.1.18, fasteners==0.19, httpx>=0.28.1)
- Uses uv for dependency management
- Python 3.10+ required
- Entry points: `fastled-wasm-compiler` and `fastled-wasm-compiler-prewarm`

## Development Workflow

1. Use `./install` to set up development environment
2. Write code following the existing patterns
3. Run `./lint` before committing to ensure code quality
4. Run `./test` to verify functionality
5. The system uses ccache for build acceleration and supports clearing cache with `--clear-ccache`

### Code Quality Command

- `codeup` - Run complete code quality check (linting + all tests). **Note**: This command can take up to 15 minutes due to Docker-based integration tests. When using automated tools, ensure timeouts are set to at least 15 minutes (900000ms).