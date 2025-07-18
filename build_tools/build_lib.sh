#!/bin/bash

set -e

# Use environment variables with defaults, matching the Python paths.py pattern
FASTLED_ROOT="${ENV_FASTLED_ROOT:-/git/fastled}"
BUILD_ROOT_BASE="${ENV_BUILD_ROOT:-/build}"

cd "${FASTLED_ROOT}-wasm"



MODES=()

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --debug)     MODES+=("DEBUG") ;;
    --quick)     MODES+=("QUICK") ;;
    --release)   MODES+=("RELEASE") ;;
    --all)       MODES=("DEBUG" "QUICK" "RELEASE"); break ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# Default to all modes
if [ ${#MODES[@]} -eq 0 ]; then
  MODES=("DEBUG" "QUICK" "RELEASE")
fi

# Deduplicate
UNIQUE_MODES=()
for mode in "${MODES[@]}"; do
  [[ " ${UNIQUE_MODES[*]} " == *" $mode "* ]] || UNIQUE_MODES+=("$mode")
done

for MODE in "${UNIQUE_MODES[@]}"; do
  echo ">>> Building in mode: $MODE"

  # Build directory in $BUILD_ROOT_BASE/<mode> (absolute)
  BUILD_DIR="${BUILD_ROOT_BASE}/${MODE,,}"

  mkdir -p "$BUILD_DIR"
  cd "$BUILD_DIR"

  export BUILD_MODE="$MODE"
  
  echo ">>> Step 1/3: Compiling object files (NO_LINK=ON)"
  export NO_THIN_LTO=0  # Use thin LTO for compilation step
  emcmake cmake "${FASTLED_ROOT}-wasm" -G Ninja -DNO_LINK=ON
  ninja -v
  
  echo ">>> Step 2/3: Linking thin archive (NO_BUILD=ON, NO_THIN_LTO=0)"
  export NO_THIN_LTO=0
  emcmake cmake "${FASTLED_ROOT}-wasm" -G Ninja -DNO_BUILD=ON
  ninja -v
  
  echo ">>> Step 3/3: Linking regular archive (NO_BUILD=ON, NO_THIN_LTO=1)"
  export NO_THIN_LTO=1
  emcmake cmake "${FASTLED_ROOT}-wasm" -G Ninja -DNO_BUILD=ON
  ninja -v

  cd -
done
