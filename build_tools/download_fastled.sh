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


# Now remove all files in ${FASTLED_ROOT}/src/platforms that isn't wasm, stub or shared
cd "${FASTLED_ROOT}/src/platforms"
shopt -s extglob  # enable extended globing
for d in */; do
  if [[ ! "$d" == *wasm* && ! "$d" == *stub* && ! "$d" == *shared* ]]; then
    rm -rf "$d"
  fi
done

cd "${FASTLED_ROOT}/src"

# now normalize all file endings encase they aren't unix.
find . \( \
  -name "*.c*" -o \
  -name "*.h" -o \
  -name "*.hpp" -o \
  -name "*.sh" -o \
  -name "*.js" -o \
  -name "*.mjs" -o \
  -name "*.css" -o \
  -name "*.txt" -o \
  -name "*.html" \
\) -print0 | xargs -0 dos2unix