#!/bin/bash

# sleep forever
source /emsdk/emsdk_env.sh
export PATH="$PATH:/emsdk/upstream/bin"

# Set container-specific environment variables for path resolution
# Use environment variables or sensible defaults for paths
# Set the FastLED root to point to the container's copy


export ENV_FASTLED_ROOT="${ENV_FASTLED_ROOT:-/git/fastled}"
export ENV_FASTLED_SRC_CONTAINER="${ENV_FASTLED_SRC_CONTAINER:-${ENV_FASTLED_ROOT:-/git/fastled}/src}"
export ENV_FASTLED_SOURCE_PATH="${ENV_FASTLED_SOURCE_PATH:-git/fastled/src}"
export ENV_EMSDK_PATH="${ENV_EMSDK_PATH:-emsdk}"
export ENV_SKETCH_PATH="${ENV_SKETCH_PATH:-src}"



# Set the volume mapped source to point to the host mount (if it exists)
# This defaults to the container's FastLED copy if no host volume is mounted
export ENV_VOLUME_MAPPED_SRC="${ENV_VOLUME_MAPPED_SRC:-/host/fastled/src}"

fastled-wasm-compiler "$@"