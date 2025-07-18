# Generated from compilation_flags.toml - DO NOT EDIT MANUALLY
# Run build_tools/generate_cmake_flags.py to regenerate

set(FASTLED_BASE_COMPILE_FLAGS
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50"
    "-DFASTLED_FORCE_NAMESPACE=1"
    "-DFASTLED_USE_PROGMEM=0"
    "-DUSE_OFFSET_CONVERTER=0"
    "-DGL_ENABLE_GET_PROC_ADDRESS=0"
    "-DEMSCRIPTEN_NO_THREADS"
    "-D_REENTRANT=0"
    "-std=gnu++17"
    "-fpermissive"
    "-Wno-constant-logical-operand"
    "-Wnon-c-typedef-for-linkage"
    "-Werror=bad-function-cast"
    "-Werror=cast-function-type"
    "-fno-threadsafe-statics"
    "-fno-exceptions"
    "-emit-llvm"
    "-Wall"
)

set(FASTLED_DEBUG_FLAGS
    "-g3"
    "-gsource-map"
    "-ffile-prefix-map=/=sketchsource/"
    "-fsanitize=address"
    "-fsanitize=undefined"
    "-fno-inline"
    "-O0"
)

set(FASTLED_QUICK_FLAGS
    "-flto=thin"
    "-O0"
    "-g0"
    "-fno-inline-functions"
    "-fno-vectorize"
    "-fno-unroll-loops"
    "-fno-strict-aliasing"
)

set(FASTLED_RELEASE_FLAGS
    "-Oz"
)

