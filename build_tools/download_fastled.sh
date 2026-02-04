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
