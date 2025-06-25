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

# Remove all downloaded archives - these are the biggest space consumers
echo "Removing downloaded archives..."
rm -rf downloads/ 2>/dev/null || true

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
rm -rf site/ 2>/dev/null || true

# Remove git history and metadata to save space
rm -rf .git/ 2>/dev/null || true
rm -rf .github/ 2>/dev/null || true

# Clean up any large log files
find . -name "*.log" -size +1M -delete 2>/dev/null || true

# Remove intermediate build files
find . -name "*.o" -delete 2>/dev/null || true
find . -name "*.a" -name "*debug*" -delete 2>/dev/null || true

# Remove debug symbols and strip binaries if strip command is available
if command -v strip >/dev/null 2>&1; then
    echo "Stripping debug symbols from binaries..."
    find . -type f -executable -exec file {} \; | grep -E "(executable|shared object)" | cut -d: -f1 | xargs -r strip --strip-debug 2>/dev/null || true
fi

# Remove unnecessary language packs and locales
rm -rf */locale/ 2>/dev/null || true
rm -rf */locales/ 2>/dev/null || true
rm -rf */i18n/ 2>/dev/null || true

# Remove source files that aren't needed for compilation
find . -name "*.cpp" -path "*/src/*" -delete 2>/dev/null || true
find . -name "*.c" -path "*/src/*" -delete 2>/dev/null || true
find . -name "*.cc" -path "*/src/*" -delete 2>/dev/null || true

# Remove large unnecessary files
find . -type f -size +50M -name "*.tar*" -delete 2>/dev/null || true
find . -type f -size +50M -name "*.zip" -delete 2>/dev/null || true

# Remove backup files
find . -name "*.bak" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true

# Remove duplicate shared libraries (keep only the most recent versions)
find . -name "*.so.*" -type f | sort | uniq -d | head -n -1 | xargs -r rm 2>/dev/null || true

echo "Cleanup completed. Checking directory size..."

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
    --exclude='*download*' \
    --exclude='*.tar*' \
    --exclude='*.zip' \
    --exclude='*.bak' \
    --exclude='*~' \
    --exclude='*/locale/*' \
    --exclude='*/locales/*' \
    -czf "${ARTIFACT_NAME}.tar.gz" emsdk

# Check the size of the created artifact
if command -v stat >/dev/null 2>&1; then
    size=$(stat -f%z "${ARTIFACT_NAME}.tar.gz" 2>/dev/null || stat -c%s "${ARTIFACT_NAME}.tar.gz" 2>/dev/null)
    size_mb=$((size / 1024 / 1024))
    echo "Created artifact: ${ARTIFACT_NAME}.tar.gz (${size_mb}MB)"
    
    if [ $size_mb -gt 95 ]; then
        echo "WARNING: Artifact is ${size_mb}MB, which is close to GitHub's ~100MB limit!"
        echo "Attempting to create split archives..."
        
        # Remove the oversized artifact
        rm "${ARTIFACT_NAME}.tar.gz"
        
        # Create split archives
        cd emsdk
        
        # Create core tools archive (essential binaries)
        echo "Creating core tools archive..."
        GZIP=-9 tar --exclude='*.git*' \
            --exclude='*cache*' \
            --exclude='*tmp*' \
            --exclude='*temp*' \
            --exclude='*.log' \
            --exclude='*test*' \
            --exclude='*doc*' \
            --exclude='*example*' \
            --exclude='*download*' \
            --exclude='*.tar*' \
            --exclude='*.zip' \
            --exclude='*.bak' \
            --exclude='*~' \
            --exclude='*/locale/*' \
            --exclude='*/locales/*' \
            --exclude='python/*' \
            --exclude='node/*' \
            -czf "../${ARTIFACT_NAME}-core.tar.gz" .
            
        # Create runtime archive (python and node)
        echo "Creating runtime dependencies archive..."
        GZIP=-9 tar --exclude='*.git*' \
            --exclude='*cache*' \
            --exclude='*tmp*' \
            --exclude='*temp*' \
            --exclude='*.log' \
            --exclude='*test*' \
            --exclude='*doc*' \
            --exclude='*example*' \
            --exclude='*download*' \
            --exclude='*.tar*' \
            --exclude='*.zip' \
            --exclude='*.bak' \
            --exclude='*~' \
            --exclude='*/locale/*' \
            --exclude='*/locales/*' \
            -czf "../${ARTIFACT_NAME}-runtime.tar.gz" python/ node/ 2>/dev/null || true
            
        cd ..
        
        # Check sizes of split archives
        for archive in "${ARTIFACT_NAME}-core.tar.gz" "${ARTIFACT_NAME}-runtime.tar.gz"; do
            if [ -f "$archive" ]; then
                size=$(stat -f%z "$archive" 2>/dev/null || stat -c%s "$archive" 2>/dev/null)
                size_mb=$((size / 1024 / 1024))
                echo "Created split artifact: $archive (${size_mb}MB)"
                
                if [ $size_mb -gt 95 ]; then
                    echo "ERROR: Split artifact $archive is still ${size_mb}MB, exceeding the limit!"
                    exit 1
                fi
            fi
        done
        
        echo "Successfully created split artifacts under the size limit."
    else
        echo "Artifact size is acceptable (${size_mb}MB < 95MB)"
    fi
fi

# Also create the artifact in the original repository directory if we're not already there
if [ "$PWD" != "$GITHUB_WORKSPACE" ] && [ -n "$GITHUB_WORKSPACE" ]; then
    cp "${ARTIFACT_NAME}"*.tar.gz "$GITHUB_WORKSPACE/" 2>/dev/null || true
fi
