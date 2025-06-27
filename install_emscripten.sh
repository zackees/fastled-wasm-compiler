#!/bin/bash

set -e

EMSDK_DIR="$HOME/emsdk"

# Set aggressive optimization flags for SDK compilation
export CFLAGS="-Oz -flto -ffunction-sections -fdata-sections -fno-exceptions -fno-rtti -fno-unwind-tables -fno-asynchronous-unwind-tables -fomit-frame-pointer -ffast-math -fno-stack-protector"
export CXXFLAGS="-Oz -flto -ffunction-sections -fdata-sections -fno-exceptions -fno-rtti -fno-unwind-tables -fno-asynchronous-unwind-tables -fomit-frame-pointer -ffast-math -fno-stack-protector"
export LDFLAGS="-Oz -flto -Wl,--gc-sections -Wl,--strip-all -Wl,--strip-debug -s"

# Additional optimization environment variables
export EMCC_OPTIMIZE_SIZE=1
export EMCC_CLOSURE=1
export CMAKE_BUILD_TYPE=MinSizeRel

echo "Setting optimization flags for SDK compilation:"
echo "CFLAGS: $CFLAGS"
echo "CXXFLAGS: $CXXFLAGS"
echo "LDFLAGS: $LDFLAGS"

if [ ! -d "$EMSDK_DIR" ]; then
    git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR" --depth=1
fi

cd "$EMSDK_DIR"
# Only pull if we have a full clone
if [ -d ".git" ]; then
    git pull
fi

# Install with optimization flags set
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

# More aggressive cleanup for maximum size reduction
echo "Applying aggressive size reduction..."

# Remove all debug information and symbols
find . -name "*.debug" -delete 2>/dev/null || true
find . -name "*.pdb" -delete 2>/dev/null || true
find . -name "*.dSYM" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove source maps and debugging files
find . -name "*.map" -delete 2>/dev/null || true
find . -name "*.dwp" -delete 2>/dev/null || true
find . -name "*.dwarf" -delete 2>/dev/null || true

# Remove unnecessary static libraries (keep only essential ones)
find . -name "*.a" -path "*/lib/*" -not -name "libc.a" -not -name "libm.a" -not -name "libpthread.a" -not -name "librt.a" -not -name "libdl.a" -delete 2>/dev/null || true

# Remove unnecessary headers and includes (keep only essential runtime headers)
find . -path "*/include/*" -name "*.h" -not -path "*/emscripten/*" -not -path "*/c++/*" -not -name "emscripten.h" -not -name "bind.h" -delete 2>/dev/null || true

# Remove language-specific files we don't need
rm -rf */locale/ 2>/dev/null || true
rm -rf */locales/ 2>/dev/null || true
rm -rf */i18n/ 2>/dev/null || true
rm -rf */po/ 2>/dev/null || true
rm -rf */share/locale/ 2>/dev/null || true

# Remove man pages and documentation
rm -rf */man/ 2>/dev/null || true
rm -rf */share/man/ 2>/dev/null || true
rm -rf */share/doc/ 2>/dev/null || true
rm -rf */share/info/ 2>/dev/null || true

# Remove unnecessary compiler tools (keep only essential ones)
find . -name "clang++-*" -not -name "clang++" -delete 2>/dev/null || true
find . -name "clang-*" -not -name "clang" -delete 2>/dev/null || true

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

# Remove unnecessary binary variants (keep only the most optimized ones)
find . -name "*-debug" -type f -delete 2>/dev/null || true
find . -name "*_debug" -type f -delete 2>/dev/null || true

# Strip debug symbols from all binaries and shared libraries
if command -v strip >/dev/null 2>&1; then
    echo "Stripping debug symbols from binaries..."
    # Fix for macOS: use different approach for finding executable files
    case "$(uname)" in
        Darwin)
            # macOS-specific approach
            find . -type f -perm +111 -exec file {} \; | grep -E "(executable|shared object)" | cut -d: -f1 | while read -r file; do
                strip -S "$file" 2>/dev/null || true
            done
            # Strip static libraries
            find . -name "*.a" -exec strip -S {} \; 2>/dev/null || true
            ;;
        Linux)
            # Linux approach
            find . -type f -executable -exec file {} \; | grep -E "(executable|shared object)" | cut -d: -f1 | xargs -r strip --strip-all 2>/dev/null || true
            # Also strip static libraries
            find . -name "*.a" -exec strip --strip-debug {} \; 2>/dev/null || true
            ;;
        *)
            # Generic approach
            find . -type f -name "*.so*" -exec strip {} \; 2>/dev/null || true
            find . -name "*.a" -exec strip {} \; 2>/dev/null || true
            ;;
    esac
fi

# Use UPX to compress binaries if available (ultra-aggressive compression)
if command -v upx >/dev/null 2>&1; then
    echo "Compressing binaries with UPX..."
    find . -type f -size +1M -exec file {} \; | grep -E "(executable|shared object)" | cut -d: -f1 | while read -r file; do
        upx --ultra-brute "$file" 2>/dev/null || true
    done
fi

# Remove duplicate shared libraries (keep only the most recent versions) - Fix head command
find . -name "*.so.*" -type f | sort | uniq -d | head -n 1 | while read -r file; do
    rm "$file" 2>/dev/null || true
done

# Remove Python optimization files
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name "*.opt-1.pyc" -delete 2>/dev/null || true
find . -name "*.opt-2.pyc" -delete 2>/dev/null || true

# Remove unnecessary Node.js modules (if any)
find . -path "*/node_modules/*" -name "*.md" -delete 2>/dev/null || true
find . -path "*/node_modules/*" -name "LICENSE*" -delete 2>/dev/null || true
find . -path "*/node_modules/*" -name "CHANGELOG*" -delete 2>/dev/null || true

# Remove CMake cache and build files
find . -name "CMakeCache.txt" -delete 2>/dev/null || true
find . -name "CMakeFiles" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.cmake" -path "*/CMakeFiles/*" -delete 2>/dev/null || true

# Remove pkg-config files we don't need
find . -name "*.pc" -path "*/pkgconfig/*" -delete 2>/dev/null || true

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

# Function to get file size in a cross-platform way
get_file_size() {
    local file="$1"
    if command -v stat >/dev/null 2>&1; then
        case "$(uname)" in
            Darwin|*BSD)
                stat -f%z "$file" 2>/dev/null
                ;;
            *)
                stat -c%s "$file" 2>/dev/null
                ;;
        esac
    else
        # Fallback: use ls and extract size
        ls -l "$file" 2>/dev/null | awk '{print $5}'
    fi
}

# Common tar exclusions
COMMON_EXCLUDES=(
    --exclude='*.git*'
    --exclude='*cache*'
    --exclude='*tmp*'
    --exclude='*temp*'
    --exclude='*.log'
    --exclude='*test*'
    --exclude='*doc*'
    --exclude='*example*'
    --exclude='*download*'
    --exclude='*.tar*'
    --exclude='*.zip'
    --exclude='*.bak'
    --exclude='*~'
    --exclude='*/locale/*'
    --exclude='*/locales/*'
    --exclude='*/man/*'
    --exclude='*/share/man/*'
    --exclude='*/share/doc/*'
    --exclude='*/share/info/*'
    --exclude='*debug*'
    --exclude='*.debug'
    --exclude='*.pdb'
    --exclude='*.dSYM'
    --exclude='*.map'
    --exclude='*.dwp'
    --exclude='*.dwarf'
    --exclude='CMakeFiles'
    --exclude='*.cmake'
    --exclude='*.pc'
)

echo "Creating compressed artifact: ${ARTIFACT_NAME}.tar.gz"

# Create a highly compressed tarball with maximum compression
echo "Using GZIP compression with maximum compression level..."
GZIP=-9 tar "${COMMON_EXCLUDES[@]}" -czf "${ARTIFACT_NAME}.tar.gz" emsdk

# Check the size of the created artifact
size=$(get_file_size "${ARTIFACT_NAME}.tar.gz")
if [ -n "$size" ] && [ "$size" -gt 0 ]; then
    size_mb=$((size / 1024 / 1024))
    echo "Created artifact: ${ARTIFACT_NAME}.tar.gz (${size_mb}MB)"
    
    if [ $size_mb -gt 95 ]; then
        echo "WARNING: Artifact is ${size_mb}MB, which is close to GitHub's ~100MB limit!"
        echo "Attempting to create split archives..."
        
        # Remove the oversized artifact
        rm "${ARTIFACT_NAME}.tar.gz"
        
        # Create split archives with more granular splitting
        cd emsdk
        
        # 1. Core Emscripten Tools (emcc, em++, basic scripts)
        echo "Creating core Emscripten tools archive..."
        GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
            --exclude='upstream/*' \
            --exclude='python/*' \
            --exclude='node/*' \
            --exclude='binaryen/*' \
            --exclude='java/*' \
            -czf "../${ARTIFACT_NAME}-core.tar.gz" . 2>/dev/null || true
            
        # 2. LLVM/Clang Backend
        echo "Creating LLVM backend archive..."
        if [ -d "upstream" ]; then
            cd upstream
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                --exclude='lib/*' \
                --exclude='share/*' \
                --exclude='include/*' \
                -czf "../../${ARTIFACT_NAME}-llvm.tar.gz" bin/ 2>/dev/null || true
            cd ..
        fi
        
        # 3. System Libraries
        echo "Creating system libraries archive..."
        if [ -d "upstream" ]; then
            cd upstream
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                -czf "../../${ARTIFACT_NAME}-libs.tar.gz" lib/ share/ include/ 2>/dev/null || true
            cd ..
        fi
        
        # 4. Python Runtime
        echo "Creating Python runtime archive..."
        if [ -d "python" ]; then
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                -czf "../${ARTIFACT_NAME}-python.tar.gz" python/ 2>/dev/null || true
        fi
        
        # 5. Node.js Runtime
        echo "Creating Node.js runtime archive..."
        if [ -d "node" ]; then
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                -czf "../${ARTIFACT_NAME}-node.tar.gz" node/ 2>/dev/null || true
        fi
        
        # 6. Binaryen Tools (wasm-opt, etc.)
        echo "Creating Binaryen tools archive..."
        if [ -d "binaryen" ]; then
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                -czf "../${ARTIFACT_NAME}-binaryen.tar.gz" binaryen/ 2>/dev/null || true
        fi
        
        # 7. Java Runtime (if exists)
        if [ -d "java" ]; then
            echo "Creating Java runtime archive..."
            GZIP=-9 tar "${COMMON_EXCLUDES[@]}" \
                -czf "../${ARTIFACT_NAME}-java.tar.gz" java/ 2>/dev/null || true
        fi
        
        cd ..
        
        # Check sizes of all split archives
        success=true
        total_size=0
        for archive in "${ARTIFACT_NAME}"-*.tar.gz; do
            if [ -f "$archive" ]; then
                size=$(get_file_size "$archive")
                if [ -n "$size" ] && [ "$size" -gt 0 ]; then
                    size_mb=$((size / 1024 / 1024))
                    total_size=$((total_size + size_mb))
                    echo "Created split artifact: $archive (${size_mb}MB)"
                    
                    if [ $size_mb -gt 95 ]; then
                        echo "ERROR: Split artifact $archive is still ${size_mb}MB, exceeding the limit!"
                        success=false
                    fi
                else
                    echo "WARNING: Could not determine size of $archive"
                fi
            fi
        done
        
        if [ "$success" = true ]; then
            echo "Successfully created split artifacts under the size limit."
            echo "Total compressed size: ${total_size}MB across $(ls "${ARTIFACT_NAME}"-*.tar.gz 2>/dev/null | wc -l) archives"
            
            # Create a manifest file listing all parts
            echo "Creating manifest file..."
            cat > "${ARTIFACT_NAME}-manifest.txt" << EOF
# EMSDK Split Archive Manifest
# This file lists all the parts of the split EMSDK archive
# Extract all parts to the same directory to reconstruct the full EMSDK

EMSDK_VERSION=$(cat emsdk/.emscripten_version 2>/dev/null || echo "unknown")
SPLIT_DATE=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
TOTAL_ARCHIVES=$(ls "${ARTIFACT_NAME}"-*.tar.gz 2>/dev/null | wc -l)

Archives:
EOF
            for archive in "${ARTIFACT_NAME}"-*.tar.gz; do
                if [ -f "$archive" ]; then
                    size=$(get_file_size "$archive")
                    size_mb=$((size / 1024 / 1024))
                    echo "  $archive (${size_mb}MB)" >> "${ARTIFACT_NAME}-manifest.txt"
                fi
            done
            
            echo ""
            echo "Extraction Instructions:" >> "${ARTIFACT_NAME}-manifest.txt"
            echo "1. Download all ${ARTIFACT_NAME}-*.tar.gz files to the same directory" >> "${ARTIFACT_NAME}-manifest.txt"
            echo "2. Extract each archive in order:" >> "${ARTIFACT_NAME}-manifest.txt"
            for archive in "${ARTIFACT_NAME}"-*.tar.gz; do
                if [ -f "$archive" ]; then
                    echo "   tar -xzf $archive" >> "${ARTIFACT_NAME}-manifest.txt"
                fi
            done
            echo "3. Run: source emsdk/emsdk_env.sh" >> "${ARTIFACT_NAME}-manifest.txt"
            
        else
            echo "ERROR: Some split artifacts are still too large!"
            exit 1
        fi
    else
        echo "Artifact size is acceptable (${size_mb}MB < 95MB)"
    fi
else
    echo "ERROR: Could not determine artifact size"
    exit 1
fi

# Also create the artifact in the original repository directory if we're not already there
if [ "$PWD" != "$GITHUB_WORKSPACE" ] && [ -n "$GITHUB_WORKSPACE" ]; then
    cp "${ARTIFACT_NAME}"*.tar.gz "$GITHUB_WORKSPACE/" 2>/dev/null || true
    cp "${ARTIFACT_NAME}"*.txt "$GITHUB_WORKSPACE/" 2>/dev/null || true
fi
