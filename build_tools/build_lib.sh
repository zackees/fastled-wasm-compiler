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
  
  if [ "${NO_THIN_LTO:-0}" = "1" ]; then
    echo ">>> NO_THIN_LTO=1: Building libfastled.a"
  else
    echo ">>> NO_THIN_LTO=0: Building libfastled-thin.a"
  fi
  
  emcmake cmake "${FASTLED_ROOT}-wasm" -G Ninja
  ninja -v

  cd -
done
