# Investigation: -emit-llvm Linking Failures

## Summary
The `-emit-llvm` flag in build_flags.toml [library] section is causing linking failures with undefined symbols during Docker builds.

## Error
```
wasm-ld: error: lto.tmp: undefined symbol: fl::ActiveStripData::Instance()
```

## Root Cause Analysis

### What -emit-llvm Does
- Generates LLVM IR bitcode instead of native object code
- Intended for LTO (Link Time Optimization) workflows
- Creates .o files containing LLVM bitcode rather than WebAssembly

### Current Build Configuration
- **Library** (libfastled.a): Compiled WITH `-emit-llvm` → LLVM bitcode .o files
- **Sketch**: Compiled WITHOUT `-emit-llvm` → Normal WebAssembly .o files

### Investigation Results
1. ✅ `active_strip_data.o` IS present in libfastled.a archive
2. ✅ Symbol `fl::ActiveStripData::Instance()` IS defined in the object file (verified with llvm-nm)
3. ✅ Object files are WebAssembly format (not pure LLVM bitcode)
4. ❌ Many object files in archive show "no symbols" with llvm-nm
5. ❌ Linker fails during LTO phase when processing mixed bitcode/wasm objects

### The Problem
When linking:
- wasm-ld attempts LTO on bitcode objects from library
- Sketch objects are pure WebAssembly (no bitcode)
- LTO phase creates `lto.tmp` intermediate but loses symbol visibility
- Mixed bitcode/wasm linking appears to cause symbol resolution failures

## Why -emit-llvm Was Added
Originally added to enable LLVM-level optimizations across the library. However:
- Emscripten already does LTO without explicit `-emit-llvm`
- The flag causes incompatibility between library and sketch object formats
- Standard Emscripten workflow doesn't require explicit `-emit-llvm` for archives

## Recommendations

### Option 1: Remove -emit-llvm (RECOMMENDED)
- Remove `-emit-llvm` from [library] section
- Library and sketch will both use standard WebAssembly objects
- LTO still works via Emscripten's built-in mechanisms
- Already tested - builds successfully without the flag

### Option 2: Add -emit-llvm to sketch (NOT RECOMMENDED)  
- Would require adding `-emit-llvm` to [sketch] section
- Makes both library and sketch use bitcode consistently
- More complex, slower builds
- Defeats purpose of separate compilation

### Option 3: Use -flto instead (ALTERNATIVE)
- Replace `-emit-llvm` with `-flto` or `-flto=thin`
- Standard way to request LTO without forcing bitcode format
- Compatible with mixed compilation units
- Emscripten handles LTO automatically

## Conclusion
The `-emit-llvm` flag should be removed from the [library] section of build_flags.toml. It was causing:
1. PCH generation failures (now fixed by filtering the flag)
2. Linking failures due to mixed object formats

Emscripten's default LTO mechanisms are sufficient for optimization without explicit `-emit-llvm`.
