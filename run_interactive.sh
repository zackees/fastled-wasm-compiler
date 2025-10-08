#!/bin/bash

# Needed by windows + git-bash.
export MSYS_NO_PATHCONV=1

docker build \
  -t niteris/fastled-wasm-compiler:local \
  .

docker run --rm -it \
  -v "$(pwd)/build_tools/build_lib.sh:/build/build_lib.sh" \
  --entrypoint bash \
  -w /build \
  -p 8235:80 \
  niteris/fastled-wasm-compiler:local

