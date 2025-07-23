# FastLED WASM Compiler: Sketch Directory Migration Design

## Executive Summary

**Objective**: Migrate sketch compilation artifacts from `/build/{mode}` to `/sketch/{mode}` to separate sketch compilation artifacts from library build artifacts, improving organization and preventing conflicts.

**Status**: Design Phase  
**Priority**: Medium  
**Complexity**: Medium (requires coordinated changes across multiple modules)

---

## Problem Statement

### Current Issues

1. **Artifact Mixing**: Library artifacts (`libfastled.a`, `libfastled-thin.a`) and sketch artifacts (`fastled.js`, `fastled.wasm`, `*.o`) are stored in the same `/build/{mode}/` directory
2. **Organizational Confusion**: Difficult to distinguish between library build artifacts and sketch compilation artifacts
3. **Potential Conflicts**: Risk of name collisions between library and sketch artifacts
4. **Incremental Build Preparation**: Need clean separation for future session-based incremental building

### Current Directory Structure
```
/build/
├── debug/
│   ├── libfastled.a          # Library artifact
│   ├── libfastled-thin.a     # Library artifact
│   ├── fastled_pch.h         # Sketch artifact
│   ├── fastled_pch.h.gch     # Sketch artifact
│   ├── fastled.js            # Sketch artifact
│   ├── fastled.wasm          # Sketch artifact
│   ├── fastled.wasm.dwarf    # Sketch artifact (debug mode)
│   └── *.o                   # Sketch artifacts (object files)
├── quick/
└── release/
```

---

## Proposed Solution

### New Directory Structure
```
/build/                       # Library artifacts only
├── debug/
│   ├── libfastled.a          # Library artifact
│   └── libfastled-thin.a     # Library artifact
├── quick/
└── release/

/sketch/                      # Sketch artifacts only
├── debug/
│   ├── fastled_pch.h         # Precompiled header
│   ├── fastled_pch.h.gch     # Precompiled header cache
│   ├── fastled.js            # Compiled JavaScript
│   ├── fastled.wasm          # WebAssembly module
│   ├── fastled.wasm.dwarf    # Debug symbols (debug mode)
│   └── *.o                   # Object files
├── quick/
└── release/
```

### Environment Variable Introduction
```bash
# New environment variable for sketch build root
ENV_SKETCH_BUILD_ROOT="/sketch"    # Default value
```

---

## Implementation Plan

### Phase 1: Infrastructure Setup

#### 1.1 Path Configuration Updates

**File**: `src/fastled_wasm_compiler/paths.py`

Add new sketch build root configuration:
```python
# Sketch build paths - separate from library builds
SKETCH_BUILD_ROOT = path_or_default("/sketch", "ENV_SKETCH_BUILD_ROOT")

def get_sketch_build_dir(build_mode: str) -> Path:
    """Get the sketch build directory for a specific mode.
    
    Args:
        build_mode: Build mode (debug, quick, release)
        
    Returns:
        Path to sketch build directory
    """
    return SKETCH_BUILD_ROOT / build_mode.lower()
```

#### 1.2 Build Mode Constants

**File**: `src/fastled_wasm_compiler/paths.py`

Add helper functions for path management:
```python
def get_library_build_dir(build_mode: str) -> Path:
    """Get the library build directory (unchanged)."""
    return BUILD_ROOT / build_mode.lower()

def get_sketch_output_files(build_mode: str) -> dict[str, Path]:
    """Get expected sketch output file paths."""
    sketch_dir = get_sketch_build_dir(build_mode)
    files = {
        "js": sketch_dir / "fastled.js",
        "wasm": sketch_dir / "fastled.wasm",
        "pch_header": sketch_dir / "fastled_pch.h",
        "pch_cache": sketch_dir / "fastled_pch.h.gch",
    }
    
    if build_mode.lower() == "debug":
        files["dwarf"] = sketch_dir / "fastled.wasm.dwarf"
    
    return files
```

### Phase 2: Core Compilation Updates

#### 2.1 Sketch Compilation Module

**File**: `src/fastled_wasm_compiler/compile_sketch.py`

Key changes needed:
```python
# Replace current BUILD_ROOT usage
# OLD: build_dir = BUILD_ROOT / build_mode.lower()
# NEW: build_dir = get_sketch_build_dir(build_mode)

def compile_cpp_to_obj(src_file: Path, build_mode: str) -> tuple[subprocess.CompletedProcess, Path, str]:
    # Change build directory location
    build_dir = get_sketch_build_dir(build_mode)  # NEW
    obj_file = build_dir / f"{src_file.stem}.o"
    # ... rest unchanged

def compile_sketch(sketch_dir: Path, build_mode: str) -> Exception | None:
    # Change output directory location  
    output_dir = get_sketch_build_dir(build_mode)  # NEW
    # ... rest unchanged
```

#### 2.2 Native Compilation Module

**File**: `src/fastled_wasm_compiler/compile_sketch_native.py`

Update the native compiler build directory logic:
```python
def compile_sketch(self, sketch_dir: Path, build_mode: str, output_dir: Path | None = None) -> Path:
    if output_dir is None:
        output_dir = sketch_dir / "fastled_js"

    # Create sketch-specific build directory
    build_dir = get_sketch_build_dir(build_mode)  # NEW
    build_dir.mkdir(parents=True, exist_ok=True)
    # ... rest unchanged
```

### Phase 3: Integration Points

#### 3.1 Main Compilation Orchestrator

**File**: `src/fastled_wasm_compiler/run_compile.py`

Update build directory resolution:
```python
def run_compile(args: Args) -> int:
    # ... existing code ...
    
    if no_platformio:
        # Use new sketch build directory
        build_dir = get_sketch_build_dir(build_mode.name.lower())  # NEW
        print(banner("No-PlatformIO sketch build directory structure"))
        print(f"✓ Using sketch compilation build directory: {build_dir}")
        print(f"✓ Library artifacts remain in: {get_library_build_dir(build_mode.name.lower())}")
    # ... rest unchanged
```

#### 3.2 Docker Container Integration

**File**: `Dockerfile`

Add the new environment variable:
```dockerfile
# Add sketch build root environment variable
ENV ENV_SKETCH_BUILD_ROOT="/sketch"

# Create sketch build directory
RUN mkdir -p /sketch
```

**File**: `docker-compose.yml`

Update volume mappings if needed:
```yaml
services:
  fastled-compiler:
    environment:
      - ENV_SKETCH_BUILD_ROOT=/sketch
    # ... existing configuration
```

### Phase 4: CLI and Testing Updates

#### 4.1 CLI Argument Processing

**File**: `src/fastled_wasm_compiler/cli.py`
**File**: `src/fastled_wasm_compiler/cli_native.py`

Update help text and documentation to reflect new directory structure.

#### 4.2 Test Suite Updates

**Files**: `tests/unit/test_*.py`, `tests/integration/test_*.py`

Update test assertions and mocks:
```python
# Update path expectations in tests
# OLD: build_dir = BUILD_ROOT / "debug"
# NEW: build_dir = get_sketch_build_dir("debug")

# Update test mocks
with patch("fastled_wasm_compiler.paths.SKETCH_BUILD_ROOT", Path("/test_sketch")):
    # ... test code
```

---

## Migration Strategy

### Backward Compatibility

1. **Environment Variable Fallback**: If `ENV_SKETCH_BUILD_ROOT` is not set, fall back to current behavior temporarily
2. **Deprecation Warnings**: Add warnings when using the old directory structure
3. **Gradual Migration**: Support both old and new paths during transition period

### Rollout Plan

1. **Phase 1** (Week 1): Implement infrastructure changes with fallback
2. **Phase 2** (Week 2): Update core compilation modules
3. **Phase 3** (Week 3): Update integration points and Docker configuration  
4. **Phase 4** (Week 4): Update tests and validate end-to-end functionality
5. **Phase 5** (Week 5): Remove fallback behavior and old path support

---

## Implementation Details

### Files Requiring Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/fastled_wasm_compiler/paths.py` | **Major** | Add SKETCH_BUILD_ROOT and helper functions |
| `src/fastled_wasm_compiler/compile_sketch.py` | **Major** | Change build directory from BUILD_ROOT to SKETCH_BUILD_ROOT |
| `src/fastled_wasm_compiler/compile_sketch_native.py` | **Medium** | Update build directory logic |
| `src/fastled_wasm_compiler/run_compile.py` | **Medium** | Update build directory resolution |
| `src/fastled_wasm_compiler/copy_files_and_output_manifest.py` | **Minor** | Update source directory for artifact copying |
| `Dockerfile` | **Minor** | Add ENV_SKETCH_BUILD_ROOT environment variable |
| `docker-compose.yml` | **Minor** | Add environment variable if needed |
| `tests/unit/test_*.py` | **Medium** | Update test assertions and mocks |
| `tests/integration/test_*.py` | **Medium** | Update integration test expectations |

### Configuration Changes

```python
# paths.py additions
SKETCH_BUILD_ROOT = path_or_default("/sketch", "ENV_SKETCH_BUILD_ROOT")

def get_sketch_build_dir(build_mode: str) -> Path:
    """Get sketch build directory for specific mode."""
    return SKETCH_BUILD_ROOT / build_mode.lower()

def get_library_build_dir(build_mode: str) -> Path:
    """Get library build directory (unchanged)."""
    return BUILD_ROOT / build_mode.lower()
```

---

## Benefits

### Immediate Benefits
1. **Clear Separation**: Library and sketch artifacts are clearly separated
2. **Reduced Confusion**: Developers can easily identify artifact types
3. **Conflict Prevention**: No risk of name collisions between library and sketch files
4. **Better Organization**: Logical grouping of related artifacts

### Future Benefits
1. **Incremental Building**: Clean foundation for session-based incremental builds
2. **Parallel Builds**: Can build libraries and sketches independently
3. **Caching Strategy**: Different caching policies for libraries vs. sketches
4. **Cleanup Operations**: Easier to clean sketch artifacts without affecting libraries

---

## Risks and Mitigation

### Risks
1. **Breaking Changes**: Could break existing workflows/scripts
2. **Docker Volume Issues**: May require volume mapping updates
3. **Test Failures**: Extensive test updates required
4. **Documentation Lag**: Docs may become outdated

### Mitigation
1. **Gradual Migration**: Support both paths during transition
2. **Comprehensive Testing**: Full test suite validation
3. **Documentation Updates**: Update all relevant docs before release
4. **Environment Variables**: Use ENV vars for flexibility

---

## Future Considerations

### Session-Based Builds
Once this migration is complete, the foundation will be ready for session-based incremental building:

```
/sketch/
├── session-{uuid}/           # Future: session-based builds
│   ├── debug/
│   ├── quick/
│   └── release/
└── current -> session-{uuid} # Future: symlink to current session
```

### Multi-Sketch Support
The new structure also prepares for potential multi-sketch compilation:

```
/sketch/
├── sketch-{hash-or-name}/    # Future: multiple sketches
│   ├── debug/
│   └── release/
└── current -> sketch-{hash}  # Future: current active sketch
```

---

## Implementation Checklist

- [ ] **Phase 1: Infrastructure**
  - [ ] Add `SKETCH_BUILD_ROOT` to `paths.py`
  - [ ] Add `get_sketch_build_dir()` helper function
  - [ ] Add `get_library_build_dir()` helper function  
  - [ ] Add `get_sketch_output_files()` helper function
  
- [ ] **Phase 2: Core Modules**
  - [ ] Update `compile_sketch.py` build directory logic
  - [ ] Update `compile_sketch_native.py` build directory logic
  - [ ] Verify PCH file paths are updated correctly
  
- [ ] **Phase 3: Integration**
  - [ ] Update `run_compile.py` build directory resolution
  - [ ] Update Docker configuration
  - [ ] Update file copying logic
  
- [ ] **Phase 4: Testing**
  - [ ] Update unit tests
  - [ ] Update integration tests
  - [ ] Validate end-to-end compilation
  - [ ] Test Docker builds
  
- [ ] **Phase 5: Documentation**
  - [ ] Update README.md
  - [ ] Update .cursorrules
  - [ ] Update any design documents
  - [ ] Validate example code

---

This design provides a clean separation between library and sketch artifacts while maintaining backward compatibility during the migration period. The new structure will serve as a solid foundation for future incremental building capabilities. 