# Streaming Timestamp Issue Analysis and Fix

## Problem Analysis

The user reported that log output showed all timestamps as identical (6.21), indicating that the `StreamingTimestamper` was not actually streaming output in real-time but instead applying timestamps to all lines at once after the process completed.

### Example of the Issue
```
6.21 CXX_FLAGS: -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50 ...
6.21 LINK_FLAGS: -fuse-ld=lld -sWASM=1 --no-entry ...
6.21 Sources: /js/src/FestivalStick.ino
6.21 Sketch directory: /js/src
6.21 Compiling: /build_tools/ccache-emcxx.sh -c -x c++ ...
6.21 Compiled /js/src/FestivalStick.ino to /js/build/quick/FestivalStick.ino.o
6.21 Linking: /build_tools/ccache-emcxx.sh -fuse-ld=lld ...
6.21 ✅ Program built at: /js/build/quick/fastled.js
```

All timestamps are exactly 6.21 seconds, meaning all output was received simultaneously.

## Root Cause

The issue was **subprocess output buffering**. When compilation tools like emscripten/clang detect that their output is being piped to another process (rather than writing directly to a terminal), they automatically switch from line buffering to **full buffering** mode for performance reasons.

This means:
- Instead of flushing output after each line
- The tools accumulate ALL output in memory
- Then flush everything at once when the process completes
- Python receives all lines simultaneously at the end

## Technical Details

### Before Fix
```python
# In open_process.py
out = subprocess.Popen(
    cmd_list,
    stdout=subprocess.PIPE,  # This triggers full buffering in child processes
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    env=env,
)
```

The compilation process would:
1. Run for ~6 seconds
2. Buffer all output internally  
3. Flush everything at 6.21 seconds
4. StreamingTimestamper received all lines at once
5. All lines got the same timestamp (6.21)

### After Fix
```python
# Force line buffering using stdbuf
if shutil.which("stdbuf"):
    final_cmd = ["stdbuf", "-oL", "-eL"] + cmd_list
    
out = subprocess.Popen(
    final_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1,  # Line buffered on Python side
    env=env,
)
```

## Solution Implemented

The fix uses `stdbuf` (if available) to override the compilation tools' buffering behavior:

- `stdbuf -oL`: Forces **line buffering** for stdout
- `stdbuf -eL`: Forces **line buffering** for stderr  
- `bufsize=1`: Ensures Python side is also line buffered

### Benefits
1. **Real-time output**: Each line appears as soon as it's generated
2. **Accurate timestamps**: Each line gets timestamped when actually received
3. **Better user experience**: Users see progress in real-time instead of waiting for completion
4. **Robust fallback**: If `stdbuf` is not available, falls back to original behavior

### Expected Result
After the fix, timestamps should show the actual progression:
```
0.15 CXX_FLAGS: -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50 ...
0.18 LINK_FLAGS: -fuse-ld=lld -sWASM=1 --no-entry ...
0.22 Sources: /js/src/FestivalStick.ino
0.25 Sketch directory: /js/src
2.45 Compiling: /build_tools/ccache-emcxx.sh -c -x c++ ...
4.12 Compiled /js/src/FestivalStick.ino to /js/build/quick/FestivalStick.ino.o
4.15 Linking: /build_tools/ccache-emcxx.sh -fuse-ld=lld ...
6.21 ✅ Program built at: /js/build/quick/fastled.js
```

## Files Modified

- `src/fastled_wasm_compiler/open_process.py`: Added stdbuf support and improved buffering control

## Testing

To verify the fix works:
1. Run a compilation process
2. Observe that timestamps now show progression over time
3. Confirm output appears in real-time rather than all at once at the end