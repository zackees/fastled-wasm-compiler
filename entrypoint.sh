#!/bin/bash

# sleep forever
source /emsdk/emsdk_env.sh
export PATH="$PATH:/emsdk/upstream/bin"

# Set container-specific environment variables for path resolution
# Use environment variables or sensible defaults for paths
export ENV_FASTLED_SRC_CONTAINER="${ENV_FASTLED_SRC_CONTAINER:-${ENV_FASTLED_ROOT:-/git/fastled}/src}"
export ENV_FASTLED_SOURCE_PATH="${ENV_FASTLED_SOURCE_PATH:-git/fastled/src}"
export ENV_EMSDK_PATH="${ENV_EMSDK_PATH:-emsdk}"
export ENV_SKETCH_PATH="${ENV_SKETCH_PATH:-src}"

fastled-wasm-compiler "$@"