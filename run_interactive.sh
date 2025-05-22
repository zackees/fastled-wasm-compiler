#!/bin/bash

docker run --rm -it \
  --entrypoint bash \
  -w /build \
  -e ENVIRONMENT=dev \
  -p 8235:80 \
  niteris/fastled-wasm-compiler:local