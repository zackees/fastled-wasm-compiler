#!/bin/bash

# Needed by windows + git-bash.
export MSYS_NO_PATHCONV=1

docker build \
  -t niteris/fastled-wasm-compiler:local \
  .

docker run --rm -it \
  -v "$(pwd)/build_tools/CMakeLists.txt:/build/CMakeLists.txt" \
  -v "$(pwd)/build_tools/CMakeLists.txt:/git/fastled-wasm/CMakeLists.txt" \
  --entrypoint bash \
  -w /build \
  -p 8235:80 \
  niteris/fastled-wasm-compiler:local

