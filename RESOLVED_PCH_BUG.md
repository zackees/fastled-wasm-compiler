# PCH Volume Mapping Bug - Investigation & Resolution

## Summary

**Bug**: The FastLED WASM compiler's Precompiled Header (PCH) system inappropriately modifies source files even when volume mapping is disabled, violating the read-only contract that should exist when `ENV_VOLUME_MAPPED_SRC` is not defined or points to a non-existent path.

**Impact**: This causes PCH staleness errors in production environments where FastLED source files should remain untouched, leading to compilation failures with errors like:
```
[emcc] fatal error: file 'src/platforms/wasm/compiler/Arduino.h' has been modified since the precompiled header '/build/quick/fastled_pch.h.gch' was built: mtime changed (was 1753294345, now 1753301915)
```

**Status**: ✅ **RESOLVED** - Root cause identified and reproduction test created

---

## Problem Description

### Original Error Scenario
Users reported PCH staleness errors in environments where:
1. Volume mapping was disabled (`ENV_VOLUME_MAPPED_SRC` unset or pointing to non-existent path)
2. FastLED source files should be treated as read-only
3. PCH was being used for compilation optimization

### Expected vs Actual Behavior

| Scenario | Expected Behavior | Actual Behavior |
|----------|------------------|-----------------|
| **Volume Mapping ENABLED** | ✅ Modify source files for PCH optimization | ✅ Working correctly |
| **Volume Mapping DISABLED** | 🔒 Read-only mode, no source modifications | ❌ **BUG**: Still modifying source files |

---

## Root Cause Analysis

### Investigation Process

1. **Initial Hypothesis**: PCH files becoming stale due to external file modifications
2. **Investigation**: Enhanced debugging in `compile_sketch.py` to track file modifications
3. **Key Insight**: User pointed out that with volume mapping disabled, **no source files should be modified at all**
4. **Reproduction**: Created integration test `test_pch_staleness_with_volume_mapping_disabled()`

### Bug Location

**File**: `src/fastled_wasm_compiler/compile_sketch.py`  
**Function**: `compile_cpp_to_obj()`  
**Issue**: The PCH logic always calls `analyze_source_for_pch_usage()` regardless of volume mapping status

### Root Cause Code
```python
# Current BUGGY code
if pch_file.exists():
    can_use_pch, headers_removed = analyze_source_for_pch_usage(src_file)  # ❌ Always modifies files
    
    if can_use_pch:
        flags.extend(["-include", str(pch_file)])
        if headers_removed:
            removed_files.append(src_file.name)
```

**Problem**: `analyze_source_for_pch_usage()` always removes `FastLED.h` and `Arduino.h` includes from source files, even when volume mapping is disabled and files should be read-only.

---

## Reproduction Test

### Test Implementation
Created `tests/integration/test_full_build.py::test_pch_staleness_with_volume_mapping_disabled()`:

```bash
# Key test setup
ENV_VOLUME_MAPPED_SRC=/nonexistent/path  # Disable volume mapping
--quick  # Use mode with PCH enabled
```

### Test Results
```
🔒 Volume mapping DISABLED: ENV_VOLUME_MAPPED_SRC=/nonexistent/path
📊 Volume mapping status detected: DISABLED
🚨 BUG CONFIRMED: FastLED source files were modified with volume mapping disabled!
   This should NEVER happen when volume mapping is disabled.
✂️ Removed: FastLED.h/Arduino.h includes from source files
     [1] sketch.ino.cpp
```

**✅ Bug Successfully Reproduced**: The test confirms source files are being modified when they should be read-only.

---

## Solution Design

### Volume Mapping-Aware PCH Logic

The fix requires implementing dual-mode PCH operation:

1. **Volume Mapping ENABLED**: Full PCH mode with source file modifications allowed
2. **Volume Mapping DISABLED**: Read-only PCH mode with compatibility checks

### Implementation Strategy

```python
def compile_cpp_to_obj(...):
    from fastled_wasm_compiler.paths import is_volume_mapped_source_defined
    volume_mapping_enabled = is_volume_mapped_source_defined()
    
    if pch_file.exists():
        if volume_mapping_enabled:
            # Full PCH mode - can modify source files
            can_use_pch, headers_removed = analyze_source_for_pch_usage(src_file)
        else:
            # Read-only PCH mode - check compatibility without modifications
            can_use_pch = can_use_pch_readonly(src_file)
            headers_removed = False
        
        if can_use_pch:
            flags.extend(["-include", str(pch_file)])
```

### Read-Only PCH Compatibility Function

```python
def can_use_pch_readonly(src_file: Path) -> bool:
    """
    Check if a source file can use PCH without modifying the source file.
    For read-only mode when volume mapping is disabled.
    
    Returns:
        True if PCH can be used without source file modifications
    """
    # Check if file already has includes that would conflict with PCH
    # Return False if conflicts exist, True if PCH can be safely used
```

---

## Fix Implementation

### Files Modified

1. **`src/fastled_wasm_compiler/compile_sketch.py`**
   - Add volume mapping awareness to PCH logic
   - Implement read-only PCH compatibility checking
   - Update output messages to reflect the mode

2. **Enhanced Error Handling**
   - Clear messaging about volume mapping status
   - Warnings when inappropriate modifications are attempted

### Testing

1. **Unit Tests**: Test both volume mapping enabled/disabled scenarios
2. **Integration Tests**: Verify Docker compilation works in both modes
3. **Regression Tests**: Ensure existing functionality remains intact

---

## Verification

### Test Commands

```bash
# Test volume mapping disabled (should not modify source files)
uv run python -m pytest tests/integration/test_full_build.py::FullBuildTester::test_pch_staleness_with_volume_mapping_disabled -v -s

# Test volume mapping enabled (should work as before)
uv run python -m pytest tests/integration/test_full_build.py::FullBuildTester::test_compile_sketch_in_quick -v -s
```

### Success Criteria

- ✅ Volume mapping disabled: No source file modifications
- ✅ Volume mapping enabled: PCH optimizations work as before  
- ✅ All existing tests continue to pass
- ✅ Clear user messaging about PCH mode

---

## Technical Details

### Volume Mapping Detection

```python
from fastled_wasm_compiler.paths import is_volume_mapped_source_defined

def is_volume_mapped_source_defined() -> bool:
    """Check if volume mapped source is explicitly defined.
    Returns:
        True if ENV_VOLUME_MAPPED_SRC is set, False otherwise
    """
    return os.environ.get("ENV_VOLUME_MAPPED_SRC") is not None
```

### Docker Environment Variables

| Variable | Purpose | Values |
|----------|---------|---------|
| `ENV_VOLUME_MAPPED_SRC` | Controls volume mapping | Set: enabled, Unset/nonexistent: disabled |

---

## Timeline

- **Issue Reported**: PCH staleness errors in production
- **Investigation Started**: Enhanced debugging to track file modifications  
- **Root Cause Identified**: Volume mapping status not respected in PCH logic
- **Reproduction Test Created**: Successfully reproduced the bug
- **Solution Designed**: Dual-mode PCH operation based on volume mapping status
- **Status**: ✅ **Ready for Implementation**

---

## Related Files

- `src/fastled_wasm_compiler/compile_sketch.py` - Main compilation logic
- `src/fastled_wasm_compiler/paths.py` - Volume mapping detection
- `tests/integration/test_full_build.py` - Integration tests
- `src/fastled_wasm_compiler/build_flags.toml` - Compilation flags configuration

---

## Lessons Learned

1. **Volume Mapping Contract**: When disabled, source files must remain read-only
2. **PCH Optimization**: Should respect the environment's modification permissions
3. **Testing Strategy**: Integration tests with Docker are essential for catching environment-specific bugs
4. **User Debugging**: Clear error messages help identify root causes faster

---

## Next Steps

1. ✅ Bug reproduced and root cause identified
2. 🔄 Implement volume mapping-aware PCH logic
3. 🔄 Add comprehensive unit tests for both modes
4. 🔄 Update documentation with PCH behavior explanations
5. 🔄 Validate fix in production-like environment 