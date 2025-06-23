#!/bin/bash

set -e

EMSDK_DIR="$HOME/emsdk"

if [ ! -d "$EMSDK_DIR" ]; then
    git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
fi

cd "$EMSDK_DIR"
git pull

./emsdk install latest
./emsdk activate latest
source ./emsdk_env.sh

emcc -v

cd ..
ARTIFACT_NAME="emsdk-$(uname | tr '[:upper:]' '[:lower:]')"
tar -czf "${ARTIFACT_NAME}.tar.gz" emsdk
