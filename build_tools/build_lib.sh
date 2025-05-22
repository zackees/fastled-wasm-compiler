#!/bin/bash

set -e

cd /git/fastled-wasm

MODES=()

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --debug)   MODES+=("DEBUG") ;;
    --quick)   MODES+=("QUICK") ;;
    --release) MODES+=("RELEASE") ;;
    --all)     MODES=("DEBUG" "QUICK" "RELEASE"); break ;;
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

  # Build directory in /build/<mode> (absolute)
  BUILD_DIR="/build/${MODE,,}"

  mkdir -p "$BUILD_DIR"
  cd "$BUILD_DIR"

  export BUILD_MODE="$MODE"
  emcmake cmake /git/fastled-wasm -G Ninja
  ninja -v

  cd -
done
