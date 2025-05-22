#!/bin/bash

set -e

FASTLED_VERSION=master

URL=https://github.com/FastLED/FastLED/archive/refs/heads/${FASTLED_VERSION}.zip


# Download latest, unzip move into position and clean up.
wget -O /git/fastled.zip ${URL} && \
    unzip /git/fastled.zip -d /git && \
    mv /git/FastLED-master /git/fastled && \
    rm /git/fastled.zip


# Now remove all files in /git/fastled/src/platforms that isn't wasm or stub
cd /git/fastled/src/platforms
shopt -s extglob  # enable extended globing
for d in */; do
  if [[ ! "$d" == *wasm* && ! "$d" == *stub* ]]; then
    rm -rf "$d"
  fi
done

cd /git/fastled/src

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