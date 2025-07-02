#!/bin/bash

# sleep forever
source /emsdk/emsdk_env.sh
export PATH="$PATH:/emsdk/upstream/bin"

# Set container-specific environment variables for path resolution
export ENV_FASTLED_SRC_CONTAINER="/git/fastled/src"
export ENV_FASTLED_SOURCE_PATH="git/fastled/src"
export ENV_EMSDK_PATH="emsdk"
export ENV_SKETCH_PATH="src"

fastled-wasm-compiler "$@"