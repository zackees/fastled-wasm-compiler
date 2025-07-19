#!/bin/bash

set -e

# Use environment variables with defaults, matching the Python paths.py pattern
FASTLED_ROOT="${ENV_FASTLED_ROOT:-/git/fastled}"
BUILD_ROOT_BASE="${ENV_BUILD_ROOT:-/build}"

cd "${FASTLED_ROOT}-wasm"

# ============================================================================
# AUTO-REGENERATE CMAKE FLAGS FROM TOML
# ============================================================================
echo ">>> Checking if cmake_flags.cmake needs regeneration..."

# Paths for TOML source and generated cmake flags
TOML_FILE="/tmp/fastled-wasm-compiler-install/src/fastled_wasm_compiler/compilation_flags.toml"
GENERATOR_SCRIPT="/tmp/fastled-wasm-compiler-install/build_tools/generate_cmake_flags.py"
CMAKE_FLAGS_FILE="${FASTLED_ROOT}-wasm/cmake_flags.cmake"

# Check if TOML file exists (it will after COPY . step in Docker)
if [ -f "$TOML_FILE" ] && [ -f "$GENERATOR_SCRIPT" ]; then
    echo ">>> Found compilation_flags.toml, checking if regeneration needed..."
    
    # Check if cmake_flags.cmake is older than compilation_flags.toml
    if [ "$CMAKE_FLAGS_FILE" -ot "$TOML_FILE" ] || [ ! -f "$CMAKE_FLAGS_FILE" ]; then
        echo ">>> Regenerating cmake_flags.cmake from compilation_flags.toml..."
        cd /tmp/fastled-wasm-compiler-install
        
        # Try multiple approaches for maximum compatibility
        regenerated=false
        
        # Approach 1: Try uv run (if package is installed)
        if command -v uv >/dev/null 2>&1; then
            echo ">>> Attempting regeneration with uv run python..."
            if uv run python build_tools/generate_cmake_flags.py > "${CMAKE_FLAGS_FILE}" 2>/dev/null; then
                regenerated=true
                echo ">>> Success: Used uv run python"
            fi
        fi
        
        # Approach 2: Direct Python with PYTHONPATH (fallback)
        if [ "$regenerated" = false ]; then
            echo ">>> Attempting regeneration with direct Python..."
            if PYTHONPATH="/tmp/fastled-wasm-compiler-install/src:$PYTHONPATH" python3 build_tools/generate_cmake_flags.py > "${CMAKE_FLAGS_FILE}" 2>/dev/null; then
                regenerated=true
                echo ">>> Success: Used direct Python with PYTHONPATH"
            fi
        fi
        
        cd "${FASTLED_ROOT}-wasm"
        
        if [ "$regenerated" = true ]; then
            echo ">>> cmake_flags.cmake regenerated successfully"
            # Verify the regenerated file
            if [ -f "$CMAKE_FLAGS_FILE" ]; then
                echo ">>> Verification: cmake_flags.cmake exists and is $(wc -l < "$CMAKE_FLAGS_FILE") lines"
            else
                echo ">>> ERROR: Failed to generate cmake_flags.cmake"
                exit 1
            fi
        else
            echo ">>> WARNING: Could not regenerate cmake_flags.cmake, using existing version"
            echo ">>> This may cause PCH flag mismatches if compilation_flags.toml was updated"
        fi
    else
        echo ">>> cmake_flags.cmake is up-to-date"
    fi
else
    echo ">>> Using existing cmake_flags.cmake (TOML source not available yet)"
fi

echo ">>> CMake flags auto-check complete"

# ============================================================================
# ORIGINAL BUILD LOGIC
# ============================================================================


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
