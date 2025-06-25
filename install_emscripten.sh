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

# Clean up unnecessary files to reduce artifact size
echo "Cleaning up unnecessary files to reduce artifact size..."

# Remove cache and temporary files
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.cache" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Remove documentation and examples that aren't needed for compilation
rm -rf docs/ 2>/dev/null || true
rm -rf tests/ 2>/dev/null || true
rm -rf test/ 2>/dev/null || true
rm -rf examples/ 2>/dev/null || true

# Remove git history and metadata to save space
rm -rf .git/ 2>/dev/null || true
rm -rf .github/ 2>/dev/null || true

# Clean up any large log files
find . -name "*.log" -size +1M -delete 2>/dev/null || true

# Remove intermediate build files
find . -name "*.o" -delete 2>/dev/null || true
find . -name "*.a" -name "*debug*" -delete 2>/dev/null || true

cd ..

# Map uname output to GitHub Actions OS names for consistency, with Mac architecture detection
case "$(uname | tr '[:upper:]' '[:lower:]')" in
  linux) 
    OS_NAME="ubuntu-latest" 
    ;;
  darwin) 
    # Detect Mac architecture
    ARCH=$(uname -m)
    case "$ARCH" in
      arm64)
        OS_NAME="macos-arm64"
        ;;
      x86_64)
        OS_NAME="macos-x86_64"
        ;;
      *)
        # Fallback to generic macos-latest for unknown architectures
        OS_NAME="macos-latest"
        ;;
    esac
    ;;
  mingw*|cygwin*|msys*) 
    OS_NAME="windows-latest" 
    ;;
  *) 
    OS_NAME="$(uname | tr '[:upper:]' '[:lower:]')" 
    ;;
esac

ARTIFACT_NAME="emsdk-${OS_NAME}"

echo "Creating compressed artifact: ${ARTIFACT_NAME}.tar.gz"

# Create a highly compressed tarball with maximum compression
echo "Using GZIP compression with maximum compression level..."
GZIP=-9 tar --exclude='*.git*' \
    --exclude='*cache*' \
    --exclude='*tmp*' \
    --exclude='*temp*' \
    --exclude='*.log' \
    --exclude='*test*' \
    --exclude='*doc*' \
    --exclude='*example*' \
    -czf "${ARTIFACT_NAME}.tar.gz" emsdk

# Check the size of the created artifact
if command -v stat >/dev/null 2>&1; then
    size=$(stat -f%z "${ARTIFACT_NAME}.tar.gz" 2>/dev/null || stat -c%s "${ARTIFACT_NAME}.tar.gz" 2>/dev/null)
    size_mb=$((size / 1024 / 1024))
    echo "Created artifact: ${ARTIFACT_NAME}.tar.gz (${size_mb}MB)"
    
    if [ $size_mb -gt 95 ]; then
        echo "ERROR: Artifact is ${size_mb}MB, which exceeds GitHub's ~100MB limit!"
        echo "Consider further cleanup or splitting the artifact."
        exit 1
    fi
fi

# Also create the artifact in the original repository directory if we're not already there
if [ "$PWD" != "$GITHUB_WORKSPACE" ] && [ -n "$GITHUB_WORKSPACE" ]; then
    cp "${ARTIFACT_NAME}.tar.gz" "$GITHUB_WORKSPACE/"
fi
