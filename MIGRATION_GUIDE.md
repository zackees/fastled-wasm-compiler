# FastLED WASM Compiler - Migration Guide

## Overview

This guide covers the migration from Docker-based Emscripten compilation to native compilation using pre-built EMSDK binaries. This change improves performance, reduces resource usage, and provides better cross-platform compatibility.

## What's Changing

### Before (Docker-based)
- ✅ Used Docker containers with full Emscripten installation
- ✅ Required Docker to be installed and running
- ✅ Large container images (~2GB+)
- ✅ Slow startup times due to container initialization
- ✅ Limited to platforms supporting Docker

### After (Native EMSDK)
- ✅ Uses pre-built EMSDK binaries for each platform
- ✅ No Docker dependency required
- ✅ Smaller downloads (~100-200MB per platform)
- ✅ Faster startup and compilation
- ✅ Works on Windows, macOS (Intel & ARM), and Linux

## Migration Steps

### 1. Understanding the New System

The new system consists of three main components:

1. **EmsdkManager** - Downloads and manages EMSDK binaries
2. **Native Compiler** - Compiles sketches using local EMSDK
3. **Platform Detection** - Automatically selects correct binaries

### 2. Code Changes Required

#### For Library Users

**Old way (Docker-based):**
```python
# Previous method using Docker containers
from fastled_wasm_compiler.compile_sketch import compile_sketch

result = compile_sketch(sketch_dir, "debug")
```

**New way (Native):**
```python
# New method using native EMSDK
from fastled_wasm_compiler.compile_sketch_native import compile_sketch_native

result = compile_sketch_native(sketch_dir, "debug")
```

#### For Advanced Users

**Manual EMSDK Management:**
```python
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager

# Get EMSDK manager
manager = get_emsdk_manager()

# Install EMSDK if needed
if not manager.is_installed():
    manager.install()

# Get environment for compilation
env_vars = manager.setup_environment()
tool_paths = manager.get_tool_paths()
```

### 3. Command Line Changes

#### Installation
```bash
# Install EMSDK automatically on first use
python -m fastled_wasm_compiler.compile_sketch_native --install-emsdk

# Or manually install
python -m fastled_wasm_compiler.emsdk_manager --install
```

#### Compilation
```bash
# Old Docker method
docker run --rm -v $(pwd):/mapped niteris/fastled-wasm-compiler --debug

# New native method  
python -m fastled_wasm_compiler.compile_sketch_native sketch_dir --mode debug
```

### 4. Environment Setup

#### EMSDK Installation Directory
By default, EMSDK is installed to `~/.fastled-emsdk`. You can customize this:

```python
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
from pathlib import Path

# Custom installation directory
manager = get_emsdk_manager(install_dir=Path("/opt/fastled-emsdk"))
```

#### Environment Variables
The system automatically sets up these environment variables:
- `EMSDK` - Path to EMSDK installation
- `EMSDK_NODE` - Path to Node.js included with EMSDK
- `PATH` - Updated to include EMSDK tools
- `CCACHE_DIR` - ccache directory for faster rebuilds

### 5. Platform-Specific Considerations

#### Windows
- EMSDK tools use `.bat` extensions automatically
- PowerShell and Command Prompt both supported
- Windows Subsystem for Linux (WSL) supported

#### macOS
- Separate binaries for Intel (x86_64) and Apple Silicon (ARM64)
- Automatic architecture detection
- Xcode command line tools recommended

#### Linux
- Ubuntu binaries work on most distributions
- Requires `tar` and `xz-utils` for archive extraction
- No additional dependencies

### 6. CI/CD Integration

#### GitHub Actions Example
```yaml
name: FastLED WASM Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest, macos-13]
        
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install FastLED WASM Compiler
      run: pip install fastled-wasm-compiler
      
    - name: Compile Sketch
      run: |
        python -m fastled_wasm_compiler.compile_sketch_native \
          examples/Blink \
          --mode quick
```

#### Docker Alternative (Optional)
For CI environments that still prefer containers:
```dockerfile
FROM python:3.11-slim

RUN pip install fastled-wasm-compiler

# EMSDK will be downloaded automatically on first use
WORKDIR /workspace
CMD ["python", "-m", "fastled_wasm_compiler.compile_sketch_native", "--help"]
```

## Testing the Migration

### Unit Tests
```bash
# Run basic unit tests
python -m pytest tests/unit/test_emsdk_manager.py
python -m pytest tests/unit/test_native_compilation.py

# Run integration tests (downloads EMSDK)
RUN_INTEGRATION_TESTS=1 python -m pytest tests/unit/test_emsdk_manager.py::TestEmsdkManagerIntegration
```

### Manual Testing
```bash
# Test EMSDK installation
python -c "
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
manager = get_emsdk_manager()
manager.install()
print('EMSDK installed successfully')
"

# Test compilation
python -m fastled_wasm_compiler.compile_sketch_native examples/Blink --mode debug
```

## Performance Comparison

| Metric | Docker | Native | Improvement |
|--------|--------|--------|-------------|
| First time setup | ~5-10 min | ~2-3 min | 2-3x faster |
| Compilation startup | ~30-60s | ~5-10s | 5-6x faster |
| Binary size | 2GB+ | 100-200MB | 10-20x smaller |
| Memory usage | 1-2GB | 200-500MB | 3-4x less |
| Cross-platform | Limited | Full | ✅ Universal |

## Troubleshooting

### Common Issues

#### 1. Download Failures
```
Error: Failed to download EMSDK archive
```
**Solution:** Check internet connection and try again. The system will retry failed downloads.

#### 2. Platform Detection Issues
```
RuntimeError: Unsupported platform FreeBSD-x86_64
```
**Solution:** Manually specify a compatible platform or file an issue for support.

#### 3. Compilation Errors
```
RuntimeError: Failed to compile: emcc: command not found
```
**Solution:** Ensure EMSDK is properly installed:
```python
from fastled_wasm_compiler.emsdk_manager import get_emsdk_manager
manager = get_emsdk_manager()
manager.install(force=True)  # Force reinstall
```

#### 4. Permission Issues (Linux/macOS)
```
PermissionError: [Errno 13] Permission denied
```
**Solution:** Install to user directory:
```python
from pathlib import Path
manager = get_emsdk_manager(install_dir=Path.home() / ".fastled-emsdk")
```

### Debug Mode
Enable verbose logging for troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

from fastled_wasm_compiler.compile_sketch_native import compile_sketch_native
```

## Migration Timeline

### Phase 1: Preparation (Current)
- ✅ New native compilation system available
- ✅ Docker system still supported
- ✅ Both systems work in parallel

### Phase 2: Transition (Next Release)
- ⏳ Native system becomes default
- ⏳ Docker system marked as deprecated
- ⏳ Migration warnings added

### Phase 3: Completion (Future Release)
- ⏳ Docker system removed
- ⏳ Native system only
- ⏳ Full platform optimization

## API Reference

### EmsdkManager
```python
class EmsdkManager:
    def __init__(self, install_dir: Optional[Path] = None)
    def is_installed(self) -> bool
    def install(self, force: bool = False) -> None
    def get_tool_paths(self) -> Dict[str, Path]
    def setup_environment(self) -> Dict[str, str]
    def create_wrapper_scripts(self, output_dir: Path) -> Dict[str, Path]
```

### NativeCompiler
```python
class NativeCompiler:
    def __init__(self, emsdk_install_dir: Optional[Path] = None)
    def compile_sketch(self, sketch_dir: Path, build_mode: str, output_dir: Optional[Path] = None) -> Path
    def compile_source_to_object(self, source_file: Path, build_mode: str, build_dir: Path) -> Path
    def link_objects_to_wasm(self, object_files: List[Path], build_mode: str, output_dir: Path, output_name: str = "fastled") -> Path
```

### Convenience Functions
```python
def compile_sketch_native(
    sketch_dir: Path,
    build_mode: str = "debug",
    output_dir: Optional[Path] = None,
    emsdk_install_dir: Optional[Path] = None
) -> Path

def get_emsdk_manager(install_dir: Optional[Path] = None) -> EmsdkManager
```

## Support

### Getting Help
- 🐛 **Issues**: [GitHub Issues](https://github.com/zackees/fastled-wasm-compiler/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/zackees/fastled-wasm-compiler/discussions)
- 📧 **Email**: For sensitive issues

### Contributing
- 🔧 **Bug Reports**: Include platform, Python version, error logs
- ✨ **Feature Requests**: Describe use case and benefits
- 🧪 **Testing**: Run integration tests on your platform
- 📝 **Documentation**: Help improve this guide

## Changelog

### Version 1.1.0 (Native EMSDK Support)
- ✅ Added EmsdkManager for binary management
- ✅ Added NativeCompiler for local compilation
- ✅ Added cross-platform binary downloads
- ✅ Added comprehensive test suite
- ✅ Maintained backward compatibility

### Version 1.0.x (Docker-based)
- ✅ Docker-based compilation system
- ✅ Container-based toolchain
- ✅ Linux-only support 