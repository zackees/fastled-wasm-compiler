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

# If no mode given, default to all
if [ ${#MODES[@]} -eq 0 ]; then
  MODES=("DEBUG" "QUICK" "RELEASE")
fi

# Deduplicate modes (in case --all overrides others)
UNIQUE_MODES=()
for mode in "${MODES[@]}"; do
  [[ " ${UNIQUE_MODES[*]} " == *" $mode "* ]] || UNIQUE_MODES+=("$mode")
done

for MODE in "${UNIQUE_MODES[@]}"; do
  echo ">>> Building in mode: $MODE"

  BUILD_DIR="build-${MODE,,}"  # lowercase dir e.g., build-debug

  mkdir -p "$BUILD_DIR"
  cd "$BUILD_DIR"

  export BUILD_MODE="$MODE"
  emcmake cmake .. -G Ninja
  ninja

  cd ..
done