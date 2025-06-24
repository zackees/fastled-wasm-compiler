Do this task, make sure you change ALL THE LINKER FLAGS as there will be copies of them in the code base. Search them all and change so that they are all identicial and have the missing linker flags, if necessary


# ccall Export Settings Report for FastLED WASM

## Overview

This report documents the build-time settings and configurations required to properly export the new `getStripPixelData` ccall function in `src/platforms/wasm/active_strip_data.cpp`.

**Context:** This function is part of FastLED's broader migration from Emscripten embind to standard C bindings (see `EMSCRIPTEN_EMBIND_TO_C_REFACTORING.md`). The ccall implementation provides an alternative to the existing embind approach for pixel data access, offering better performance and compatibility.

## Function Signature

```cpp
extern "C" EMSCRIPTEN_KEEPALIVE 
uint8_t* getStripPixelData(int stripIndex, int* outSize);
```

## Required Build Settings

### 1. Compilation Flag

**Enable the ccall implementation:**
```bash
-DFASTLED_WASM_USE_CCALL
```

This flag must be defined during compilation to use the ccall approach instead of the embind approach.

### 2. Emscripten Export Settings

**Export the function explicitly:**
```bash
-sEXPORTED_FUNCTIONS="['_getStripPixelData', '_malloc', '_free']"
```

⚠️ **Critical:** The function name is prefixed with underscore (`_getStripPixelData`) in the exported symbols due to C name mangling.

### 3. Runtime Method Exports

**Enable ccall and cwrap:**
```bash
-sEXPORTED_RUNTIME_METHODS="['ccall', 'cwrap', 'getValue', 'HEAPU8']"
```

**Required methods breakdown:**
- `ccall` - Direct function calling from JavaScript
- `cwrap` - Function wrapping for easier JavaScript usage  
- `getValue` - Reading integer values from memory (for `outSize` parameter)
- `HEAPU8` - Uint8 memory view (for pixel data access)

### 4. Memory Management Settings

**Allow dynamic memory allocation:**
```bash
-sALLOW_MEMORY_GROWTH=1
```

Required because JavaScript needs to allocate memory for the `outSize` parameter.

**Set initial memory size (optional but recommended):**
```bash
-sINITIAL_MEMORY=16777216
```

### 5. Complete Build Command Example

```bash
emcc src/platforms/wasm/active_strip_data.cpp \
  -DFASTLED_WASM_USE_CCALL \
  -sEXPORTED_FUNCTIONS="['_getStripPixelData', '_malloc', '_free']" \
  -sEXPORTED_RUNTIME_METHODS="['ccall', 'cwrap', 'getValue', 'HEAPU8']" \
  -sALLOW_MEMORY_GROWTH=1 \
  -sINITIAL_MEMORY=16777216 \
  -o fastled.js
```

## JavaScript Usage Pattern

With proper export settings, the function can be called from JavaScript:

```javascript
// Allocate memory for output size
let sizePtr = Module._malloc(4);

// Call the exported function
let dataPtr = Module.ccall('getStripPixelData', 'number', ['number', 'number'], [stripIndex, sizePtr]);

if (dataPtr !== 0) {
    // Read the size value
    let size = Module.getValue(sizePtr, 'i32');
    
    // Create view of pixel data
    let pixelData = new Uint8Array(Module.HEAPU8.buffer, dataPtr, size);
    
    // Use pixelData...
}

// Clean up
Module._free(sizePtr);
```

## Alternative: Using cwrap

For cleaner JavaScript code, you can wrap the function:

```javascript
// Wrap the function once
const getStripPixelData = Module.cwrap('getStripPixelData', 'number', ['number', 'number']);

// Use it multiple times
let sizePtr = Module._malloc(4);
let dataPtr = getStripPixelData(stripIndex, sizePtr);
// ... rest of usage pattern
```

## Verification Steps

### 1. Check Export Success

Verify the function is properly exported:

```javascript
console.log('getStripPixelData exported:', '_getStripPixelData' in Module);
console.log('ccall available:', 'ccall' in Module);
```

### 2. Test Function Call

```javascript
// Test with invalid strip index (should return null/0)
let testPtr = Module._malloc(4);
let result = Module.ccall('getStripPixelData', 'number', ['number', 'number'], [-1, testPtr]);
console.log('Test result (should be 0):', result);
Module._free(testPtr);
```

## Common Issues and Solutions

### Issue 1: Function Not Found
**Error:** `Module.ccall is not a function` or `_getStripPixelData not exported`

**Solution:** Ensure all export flags are properly set in build command.

### Issue 2: Memory Access Errors
**Error:** Invalid memory access when reading pixel data

**Solution:** 
- Verify `ALLOW_MEMORY_GROWTH=1` is set
- Check that `HEAPU8` is exported in runtime methods
- Ensure proper memory allocation for `outSize` parameter

### Issue 3: Compilation Errors
**Error:** `EMSCRIPTEN_KEEPALIVE` not recognized

**Solution:** Include proper Emscripten headers:
```cpp
#include <emscripten.h>
#include <emscripten/emscripten.h>
```

## Build System Integration

### Existing WASM Infrastructure

FastLED currently has WASM support through various platform files in `src/platforms/wasm/`. The project uses standard C bindings as documented in the `EMSCRIPTEN_EMBIND_TO_C_REFACTORING.md`. This ccall function integrates with the existing infrastructure.

**Note:** As of October 2024, the emscripten target is under active development. A complete WASM build system is not yet implemented in the main FastLED build pipeline.

### CMake Configuration

If using CMake, add these settings:

```cmake
if(FASTLED_WASM_USE_CCALL)
    target_compile_definitions(fastled PRIVATE FASTLED_WASM_USE_CCALL)
    
    set_target_properties(fastled PROPERTIES 
        LINK_FLAGS "-sEXPORTED_FUNCTIONS=['_getStripPixelData','_malloc','_free'] \
                   -sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','getValue','HEAPU8'] \
                   -sALLOW_MEMORY_GROWTH=1"
    )
endif()
```

### PlatformIO Configuration

Add to `platformio.ini`:

```ini
[env:wasm_ccall]
build_flags = 
    -DFASTLED_WASM_USE_CCALL
    -sEXPORTED_FUNCTIONS="['_getStripPixelData','_malloc','_free']"
    -sEXPORTED_RUNTIME_METHODS="['ccall','cwrap','getValue','HEAPU8']"
    -sALLOW_MEMORY_GROWTH=1
```

### Integration with Existing WASM Functions

The ccall function should be exported alongside the existing C binding functions already documented in the refactoring guide:

```bash
-sEXPORTED_FUNCTIONS="['_getStripPixelData', '_getPixelData_Uint8_Raw', '_jsUpdateUiComponents', '_fastled_declare_files', '_malloc', '_free']"
```

## Performance Considerations

- **ccall overhead:** Each call has marshalling overhead
- **Memory allocation:** JavaScript-side memory allocation for `outSize` parameter
- **Data copying:** The returned pointer provides zero-copy access to pixel data

## Security Considerations

- Function is exported globally and accessible from any JavaScript context
- Direct memory access through returned pointers
- No bounds checking on `stripIndex` parameter from JavaScript side

## Conclusion

Proper export of the `getStripPixelData` ccall function requires careful coordination of multiple Emscripten build settings. The key requirements are:

1. Define `FASTLED_WASM_USE_CCALL` compilation flag
2. Export the function with underscore prefix in `EXPORTED_FUNCTIONS`
3. Include all necessary runtime methods in `EXPORTED_RUNTIME_METHODS`
4. Enable memory growth for dynamic allocation
5. Ensure proper JavaScript usage pattern with memory management

Following these settings will enable efficient pixel data access from JavaScript while maintaining the zero-copy performance characteristics critical for real-time LED rendering.
