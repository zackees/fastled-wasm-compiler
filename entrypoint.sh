#!/bin/bash

# sleep forever
source /emsdk/emsdk_env.sh
export PATH="$PATH:/emsdk/upstream/bin"

# Environment variables are now set in the Dockerfile

fastled-wasm-compiler "$@"