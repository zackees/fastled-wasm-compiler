#!/bin/bash

cd /git/fastled-wasm
mkdir build && cd build
export BUILD_MODE=DEBUG    # or QUICK (default), or RELEASE
cmake .. -G Ninja
ninja
