#!/bin/bash

# sleep forever
source /emsdk/emsdk_env.sh
export PATH="$PATH:/emsdk/upstream/bin"

fastled-wasm-compiler "$@"