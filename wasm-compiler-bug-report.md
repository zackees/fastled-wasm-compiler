# Bug Report: WASM Compiler Using Stale Cached Source Files

## Summary
The WASM compiler is compiling stale/cached versions of source files instead of the current working tree files, leading to compilation errors for code that doesn't exist in the current version.

## Environment
- Platform: Windows (MSYS_NT-10.0-19045)
- Compiler: fastled-wasm-compiler (via `uv run ci/wasm_compile.py`)
- Project: FastLED2
- Working directory: `C:\Users\niteris\dev\fastled2`

## Steps to Reproduce
1. Modify a sketch file (e.g., `examples/PitchDetection/PitchDetection.ino`)
2. Save changes to working tree
3. Run: `uv run ci/wasm_compile.py examples/PitchDetection --just-compile`
4. Observe compilation errors

## Expected Behavior
The compiler should compile the current version of the source file from the working tree.

## Actual Behavior
The compiler compiles an older cached version of the source file, resulting in compilation errors for code that doesn't exist in the current file.

## Evidence

### Current Working Tree File
The current `examples/PitchDetection/PitchDetection.ino` does NOT contain:
- `currentFrequency` variable
- `midiToFreq()` function
- `noteHistory` array
- `historyIndex` variable
- `HISTORY_SIZE` constant
- `displayMode` UI element
- `drawLinear()`, `drawCircular()`, `drawPianoRoll()`, `drawFrequencySpectrum()` functions

### Compilation Errors
The compiler reports errors for undeclared identifiers that don't exist in the current file:

```
/js/src/PitchDetection.ino.cpp:173:9: error: use of undeclared identifier 'currentFrequency'
/js/src/PitchDetection.ino.cpp:173:28: error: use of undeclared identifier 'midiToFreq'
/js/src/PitchDetection.ino.cpp:177:9: error: use of undeclared identifier 'noteHistory'
/js/src/PitchDetection.ino.cpp:177:21: error: use of undeclared identifier 'historyIndex'
/js/src/PitchDetection.ino.cpp:178:45: error: use of undeclared identifier 'HISTORY_SIZE'
/js/src/PitchDetection.ino.cpp:188:22: error: use of undeclared identifier 'currentFrequency'
/js/src/PitchDetection.ino.cpp:228:13: error: use of undeclared identifier 'currentFrequency'
/js/src/PitchDetection.ino.cpp:228:32: error: use of undeclared identifier 'midiToFreq'
/js/src/PitchDetection.ino.cpp:233:12: error: use of undeclared identifier 'displayMode'
/js/src/PitchDetection.ino.cpp:235:13: error: use of undeclared identifier 'drawLinear'
/js/src/PitchDetection.ino.cpp:238:13: error: use of undeclared identifier 'drawCircular'
/js/src/PitchDetection.ino.cpp:241:13: error: use of undeclared identifier 'drawPianoRoll'
/js/src/PitchDetection.ino.cpp:244:13: error: use of undeclared identifier 'drawFrequencySpectrum'
```

These line numbers and identifiers correspond to the OLD version of the file (confirmed via `git diff`).

### Git Status
```
M examples/PitchDetection/PitchDetection.ino
```

The file has uncommitted changes that ARE present in the working tree but NOT being compiled.

## Cache Location
The compiler appears to be caching source files in `/js/src/PitchDetection.ino.cpp` (inside Docker container), but this cached version is stale.

## Attempted Workarounds
- `--purge` flag: Started to run but was interrupted (unclear if this would resolve the issue)
- `--no-cache` flag: Not recognized by the compiler

## Suggested Fix
The WASM compiler should either:
1. Always read source files from the mounted working tree (not cache them), OR
2. Properly invalidate the cache when source files are modified, OR
3. Provide a reliable `--force-rebuild` or `--no-cache` flag to bypass cache

## Additional Notes
This is a critical bug as it makes iterative development impossible - developers cannot test their changes without the compiler using stale code.
