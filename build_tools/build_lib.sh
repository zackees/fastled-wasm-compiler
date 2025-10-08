#!/bin/bash

set -e

# Use environment variables with defaults, matching the Python paths.py pattern
FASTLED_ROOT="${ENV_FASTLED_ROOT:-/git/fastled}"
BUILD_ROOT_BASE="${ENV_BUILD_ROOT:-/build}"

cd "${FASTLED_ROOT}"

# ============================================================================
# NATIVE PYTHON COMPILER - NO CMAKE/NINJA REQUIRED
# ============================================================================
echo ">>> Building FastLED libraries with native Python compiler"

MODES=()
ARCHIVE_BUILD_MODE="regular"  # Default: regular archives only (best performance)

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --thin-only)     ARCHIVE_BUILD_MODE="thin" ;;
    --regular-only)  ARCHIVE_BUILD_MODE="regular" ;;
    --debug)         MODES+=("debug") ;;
    --quick)         MODES+=("quick") ;;
    --release)       MODES+=("release") ;;
    --all)           MODES=("debug" "quick" "release"); break ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# Default to all modes
if [ ${#MODES[@]} -eq 0 ]; then
  MODES=("debug" "quick" "release")
fi

# Deduplicate
UNIQUE_MODES=()
for mode in "${MODES[@]}"; do
  [[ " ${UNIQUE_MODES[*]} " == *" $mode "* ]] || UNIQUE_MODES+=("$mode")
done

# Set environment variable for the chosen archive mode
export ARCHIVE_BUILD_MODE="$ARCHIVE_BUILD_MODE"

# Validate archive mode configuration
case "$ARCHIVE_BUILD_MODE" in
  "thin")
    echo ">>> EXCLUSIVE MODE: Building ONLY thin archives"
    ;;
  "regular")
    echo ">>> EXCLUSIVE MODE: Building ONLY regular archives"
    ;;
  "both")
    echo ">>> DUAL MODE: Building BOTH archive types"
    ;;
esac

echo ">>> Using native Python compiler (no CMake/Ninja)"
echo ">>> Source: ${FASTLED_ROOT}/src"
echo ">>> Build root: ${BUILD_ROOT_BASE}"

# Build all modes using the native Python compiler
for mode in "${UNIQUE_MODES[@]}"; do
  echo ""
  echo "========================================="
  echo ">>> Building mode: $mode"
  echo ">>> Archive type: $ARCHIVE_BUILD_MODE"
  echo "========================================="

  BUILD_DIR="${BUILD_ROOT_BASE}/${mode}"
  mkdir -p "$BUILD_DIR"

  # Use the native Python compiler
  # Note: Paths come from environment variables (ENV_FASTLED_ROOT, ENV_BUILD_ROOT)
  case "$ARCHIVE_BUILD_MODE" in
    "thin")
      python3 -m fastled_wasm_compiler.native_compile_lib --${mode} --thin
      ;;
    "regular")
      python3 -m fastled_wasm_compiler.native_compile_lib --${mode}
      ;;
    "both")
      # Build thin first
      python3 -m fastled_wasm_compiler.native_compile_lib --${mode} --thin

      # Then regular (reuses cached objects)
      python3 -m fastled_wasm_compiler.native_compile_lib --${mode}
      ;;
  esac

  echo ">>> Build complete for $mode"
done

echo ""
echo "========================================="
echo ">>> All builds completed successfully!"
echo "========================================="
