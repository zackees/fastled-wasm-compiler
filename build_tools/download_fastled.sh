#!/bin/bash

set -e

# Use environment variables with defaults, matching the Python paths.py pattern
FASTLED_ROOT="${ENV_FASTLED_ROOT:-/git/fastled}"

FASTLED_VERSION=master

URL=https://github.com/FastLED/FastLED/archive/refs/heads/${FASTLED_VERSION}.zip


# Download latest, unzip move into position and clean up.
wget -O "${FASTLED_ROOT}.zip" ${URL} && \
    unzip "${FASTLED_ROOT}.zip" -d "$(dirname "${FASTLED_ROOT}")" && \
    mv "$(dirname "${FASTLED_ROOT}")/FastLED-master" "${FASTLED_ROOT}" && \
    rm "${FASTLED_ROOT}.zip"

# Temporarily disable FL_ALIGN_AS for Emscripten builds
sed -i '/^#ifdef __EMSCRIPTEN__/,/^#endif/{s/#define FL_ALIGN_AS(T) alignas(alignof(T))/#define FL_ALIGN_AS(T)/}' "${FASTLED_ROOT}/src/fl/align.h"

# Fix FL_DBG compilation error in js_bindings.cpp (comment out problematic debug line)
sed -i 's/FL_DBG("Canvas map data: " << jsonBuffer\.c_str());/\/\/ FL_DBG("Canvas map data: " << jsonBuffer.c_str());/g' "${FASTLED_ROOT}/src/platforms/wasm/js_bindings.cpp"


# Now remove all files in ${FASTLED_ROOT}/src/platforms that isn't wasm, stub, shared, posix, arm, or apollo3
# But keep is_*.h files and their local dependencies (needed by platforms/is_platform.h)
# Also keep interface headers (i*.h) needed by shared/mock implementations
cd "${FASTLED_ROOT}/src/platforms"
shopt -s extglob  # enable extended globing
for d in */; do
  if [[ ! "$d" == *wasm* && ! "$d" == *stub* && ! "$d" == *shared* && ! "$d" == *posix* && ! "$d" == *arm* && ! "$d" == *apollo3* ]]; then
    # Before removing, copy any files that need to be preserved:
    # 1. is_*.h - Platform detection headers included by platforms/is_platform.h
    # 2. i*.h - Interface headers needed by shared/mock implementations (e.g., iuart_peripheral.h)
    # 3. esp_version.h - Required by is_esp.h
    tmp_dir="${d%/}_preserved_tmp"
    mkdir -p "$tmp_dir"

    # Find and copy all is_*.h and i*.h files recursively, preserving directory structure
    # This handles both top-level and nested headers like esp/32/drivers/uart/iuart_peripheral.h
    find "$d" -name 'is_*.h' -o -name 'i*.h' 2>/dev/null | while read -r f; do
      if [ -f "$f" ]; then
        rel_path="${f#$d}"
        target_dir="$tmp_dir/$(dirname "$rel_path")"
        mkdir -p "$target_dir"
        cp "$f" "$target_dir/" 2>/dev/null || true
      fi
    done

    # Copy esp_version.h if this is the esp platform (required by is_esp.h)
    if [[ "$d" == "esp/" && -f "${d}esp_version.h" ]]; then
      cp "${d}esp_version.h" "$tmp_dir/" 2>/dev/null || true
    fi

    # Check if we found any files to preserve
    has_files=$(find "$tmp_dir" -type f 2>/dev/null | head -1)

    rm -rf "$d"

    # Restore the preserved files
    if [ -n "$has_files" ]; then
      mkdir -p "$d"
      cp -r "$tmp_dir"/* "$d" 2>/dev/null || true
    fi
    rm -rf "$tmp_dir" 2>/dev/null || true
  fi
done

cd "${FASTLED_ROOT}/src"

# Every file that is NOT *.cpp, *.hpp, *.h, *.c, *.sh, *.js, *.mjs, *.css, *.txt, *.html... get's removed.
# Gets removed

find . -type f ! \( \
  -name "*.cpp"  -o \
  -name "*.hpp"  -o \
  -name "*.h"    -o \
  -name "*.c"    -o \
  -name "*.sh"   -o \
  -name "*.js"   -o \
  -name "*.mjs"  -o \
  -name "*.css"  -o \
  -name "*.txt"  -o \
  -name "*.html" -o \
  -name "*.toml" \
\) -delete

# now normalize all file endings that remain
#dos2unix --recursive .
find . -type f -exec sed -i 's/\r$//' {} +
