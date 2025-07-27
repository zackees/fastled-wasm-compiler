# Generated from build_flags.toml - DO NOT EDIT MANUALLY
# Run build_tools/generate_cmake_flags.py to regenerate

set(FASTLED_BASE_COMPILE_FLAGS
    "-DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50"
    "-DFASTLED_FORCE_NAMESPACE=1"
    "-DFASTLED_USE_PROGMEM=0"
    "-DUSE_OFFSET_CONVERTER=0"
    "-DGL_ENABLE_GET_PROC_ADDRESS=0"
    "-D_REENTRANT=1"
    "-DEMSCRIPTEN_HAS_UNBOUND_TYPE_NAMES=0"
    "-DFASTLED_HAS_NETWORKING=1"
    "-std=gnu++17"
    "-fpermissive"
    "-Wno-constant-logical-operand"
    "-Wnon-c-typedef-for-linkage"
    "-Werror=bad-function-cast"
    "-Werror=cast-function-type"
    "-fno-threadsafe-statics"
    "-fno-exceptions"
    "-fno-rtti"
    "-pthread"
    "-fpch-instantiate-templates"
    "-emit-llvm"
    "-Wall"
)

set(FASTLED_DEBUG_FLAGS
    "-g3"
    "-gsource-map"
    "-fno-inline"
    "-O0"
    "-ffile-prefix-map=/=sketchsource/"
)

set(FASTLED_QUICK_FLAGS
    "-O1"
    "-g0"
    "-fno-inline-functions"
    "-fno-vectorize"
    "-fno-unroll-loops"
    "-fno-strict-aliasing"
    "-fno-merge-constants"
    "-fno-merge-all-constants"
    "-fno-delayed-template-parsing"
    "-fmax-type-align=4"
    "-ffast-math"
    "-fno-math-errno"
    "-fno-exceptions"
    "-fno-rtti"
)

set(FASTLED_RELEASE_FLAGS
    "-Oz"
)

