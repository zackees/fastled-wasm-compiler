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

# Map uname output to GitHub Actions OS names for consistency
case "$(uname | tr '[:upper:]' '[:lower:]')" in
  linux) OS_NAME="ubuntu-latest" ;;
  darwin) OS_NAME="macos-latest" ;;
  mingw*|cygwin*|msys*) OS_NAME="windows-latest" ;;
  *) OS_NAME="$(uname | tr '[:upper:]' '[:lower:]')" ;;
esac

ARTIFACT_NAME="emsdk-${OS_NAME}"
tar -czf "${ARTIFACT_NAME}.tar.gz" emsdk

# Also create the artifact in the original repository directory if we're not already there
if [ "$PWD" != "$GITHUB_WORKSPACE" ] && [ -n "$GITHUB_WORKSPACE" ]; then
    cp "${ARTIFACT_NAME}.tar.gz" "$GITHUB_WORKSPACE/"
fi
