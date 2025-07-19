# FastLED WASM Shared Build Settings
# This file contains compilation settings shared between sketch and library builds
# while keeping linking settings separate.

cmake_minimum_required(VERSION 3.10)

# ================================================================================================
# COMPILER TOOLCHAIN SETUP
# ================================================================================================

set(CMAKE_C_COMPILER   "emcc")
set(CMAKE_CXX_COMPILER "em++") 
set(CMAKE_AR           "emar")
set(CMAKE_RANLIB       "emranlib")

# Use ccache for faster rebuilds if available
find_program(CCACHE_EXECUTABLE ccache)
if(CCACHE_EXECUTABLE)
    set(CMAKE_C_COMPILER_LAUNCHER   "${CCACHE_EXECUTABLE}")
    set(CMAKE_CXX_COMPILER_LAUNCHER "${CCACHE_EXECUTABLE}")
    message(STATUS "Using ccache: ${CCACHE_EXECUTABLE}")
endif()

# ================================================================================================
# LINKER SELECTION
# ================================================================================================

# Check for LINKER environment variable first
if(DEFINED ENV{LINKER})
    set(SELECTED_LINKER $ENV{LINKER})
    message(STATUS "Using linker from LINKER environment variable: ${SELECTED_LINKER}")
else()
    # Auto-detect linker
    find_program(MOLD_EXECUTABLE mold)
    if(MOLD_EXECUTABLE)
        set(SELECTED_LINKER "mold")
        message(STATUS "Auto-detected mold linker: ${MOLD_EXECUTABLE}")
    else()
        find_program(LLDLINK_EXECUTABLE lld-link)
        if(LLDLINK_EXECUTABLE)
            set(SELECTED_LINKER "lld")
            message(STATUS "Auto-detected lld-link linker: ${LLDLINK_EXECUTABLE}")
        else()
            set(SELECTED_LINKER "lld")  # Default for emscripten
            message(STATUS "No specific linker found, using emscripten default: lld")
        endif()
    endif()
endif()

# ================================================================================================
# FASTLED SOURCE PATH DETECTION
# ================================================================================================

# Try to get FastLED source path from Python module
find_program(PYTHON_EXECUTABLE python3 python)
if(PYTHON_EXECUTABLE)
    execute_process(
        COMMAND ${PYTHON_EXECUTABLE} -c "from src.fastled_wasm_compiler.paths import get_fastled_source_path; print(get_fastled_source_path())"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE FASTLED_SRC_PATH
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
endif()

# Fallback if Python detection fails
if(NOT FASTLED_SRC_PATH OR FASTLED_SRC_PATH STREQUAL "")
    if(DEFINED ENV{ENV_FASTLED_ROOT})
        set(FASTLED_SRC_PATH "$ENV{ENV_FASTLED_ROOT}/src")
    else()
        set(FASTLED_SRC_PATH "/fastled/src")  # Container default
    endif()
    message(WARNING "Could not detect FastLED source path via Python, using fallback: ${FASTLED_SRC_PATH}")
else()
    message(STATUS "Detected FastLED source path: ${FASTLED_SRC_PATH}")
endif()

# ================================================================================================
# SHARED COMPILATION FLAGS
# ================================================================================================

# Base defines shared by all compilation
set(SHARED_DEFINES
    -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50
    -DFASTLED_FORCE_NAMESPACE=1
    -DFASTLED_USE_PROGMEM=0
    -DUSE_OFFSET_CONVERTER=0
    -DGL_ENABLE_GET_PROC_ADDRESS=0
    # Threading disabled flags
    -DEMSCRIPTEN_NO_THREADS
    -D_REENTRANT=0
    # Emscripten type name handling
    -DEMSCRIPTEN_HAS_UNBOUND_TYPE_NAMES=0
)

# Base compiler flags shared by all compilation
set(SHARED_COMPILER_FLAGS
    -std=gnu++17
    -fpermissive
    -Wno-constant-logical-operand
    -Wnon-c-typedef-for-linkage
    -Werror=bad-function-cast
    -Werror=cast-function-type
    -fno-threadsafe-statics  # Disable thread-safe static initialization
)

# Base include directories
set(SHARED_INCLUDE_DIRS
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${FASTLED_SRC_PATH}
    ${FASTLED_SRC_PATH}/platforms/wasm/compiler
)

# ================================================================================================
# SKETCH-SPECIFIC FLAGS
# ================================================================================================

set(SKETCH_DEFINES
    -DSKETCH_COMPILE=1
    -DFASTLED_WASM_USE_CCALL
)

set(SKETCH_COMPILER_FLAGS
    # Additional sketch-specific compiler flags (if any)
)

# ================================================================================================
# LIBRARY-SPECIFIC FLAGS  
# ================================================================================================

set(LIBRARY_DEFINES
    # Library-specific defines (if any)
)

set(LIBRARY_COMPILER_FLAGS
    -fno-rtti
    -fno-exceptions
    -emit-llvm  # Generate LLVM bitcode for library compilation
    -Wall
)

# ================================================================================================
# BUILD MODE FLAGS
# ================================================================================================

set(DEBUG_FLAGS
    -g3
    -gsource-map
    -ffile-prefix-map=/=sketchsource/
    -fsanitize=address
    -fsanitize=undefined
    -fno-inline
    -O0
)

set(QUICK_FLAGS
    -flto=thin
    -O0
    -g0
    -fno-inline-functions
    -fno-vectorize
    -fno-unroll-loops
    -fno-strict-aliasing
)

set(RELEASE_FLAGS
    -Oz
)

# ================================================================================================
# BASE LINKING FLAGS (SHARED)
# ================================================================================================

set(SHARED_LINK_FLAGS
    -fuse-ld=${SELECTED_LINKER}
    -sWASM=1
    # Threading disabled flags
    -sUSE_PTHREADS=0
)

# ================================================================================================
# SKETCH-SPECIFIC LINKING FLAGS
# ================================================================================================

set(SKETCH_LINK_FLAGS
    --no-entry
    --emit-symbol-map
    -sMODULARIZE=1
    -sEXPORT_NAME=fastled
    -sALLOW_MEMORY_GROWTH=1
    -sINITIAL_MEMORY=134217728  # 128 MB
    -sAUTO_NATIVE_LIBRARIES=0
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8','HEAPU8','getValue']"
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files','_getStripPixelData']"
    -sEXIT_RUNTIME=0
    -sFILESYSTEM=0
    -Wl,--gc-sections
    --source-map-base=http://localhost:8000/
)

# Debug-specific linking flags
set(DEBUG_LINK_FLAGS
    -fsanitize=address
    -fsanitize=undefined
    -sSEPARATE_DWARF_URL=fastled.wasm.dwarf
    -sSTACK_OVERFLOW_CHECK=2
    -sASSERTIONS=1
)

# ================================================================================================
# HELPER FUNCTIONS
# ================================================================================================

# Function to apply shared compilation flags to a target
function(apply_shared_compilation_flags target_name compilation_type)
    # Apply shared defines and compiler flags
    target_compile_definitions(${target_name} PRIVATE ${SHARED_DEFINES})
    target_compile_options(${target_name} PRIVATE ${SHARED_COMPILER_FLAGS})
    target_include_directories(${target_name} PRIVATE ${SHARED_INCLUDE_DIRS})
    
    # Apply type-specific flags
    if(compilation_type STREQUAL "sketch")
        target_compile_definitions(${target_name} PRIVATE ${SKETCH_DEFINES})
        target_compile_options(${target_name} PRIVATE ${SKETCH_COMPILER_FLAGS})
    elseif(compilation_type STREQUAL "library")
        target_compile_definitions(${target_name} PRIVATE ${LIBRARY_DEFINES})
        target_compile_options(${target_name} PRIVATE ${LIBRARY_COMPILER_FLAGS})
    else()
        message(FATAL_ERROR "Invalid compilation_type: ${compilation_type}. Must be 'sketch' or 'library'")
    endif()
    
    # Apply build mode flags
    if(CMAKE_BUILD_TYPE STREQUAL "DEBUG")
        target_compile_options(${target_name} PRIVATE ${DEBUG_FLAGS})
    elseif(CMAKE_BUILD_TYPE STREQUAL "QUICK")
        target_compile_options(${target_name} PRIVATE ${QUICK_FLAGS})
    elseif(CMAKE_BUILD_TYPE STREQUAL "RELEASE")
        target_compile_options(${target_name} PRIVATE ${RELEASE_FLAGS})
    endif()
endfunction()

# Function to apply shared linking flags to a target
function(apply_shared_linking_flags target_name compilation_type)
    # Apply shared linking flags
    target_link_options(${target_name} PRIVATE ${SHARED_LINK_FLAGS})
    
    # Apply type-specific linking flags
    if(compilation_type STREQUAL "sketch")
        target_link_options(${target_name} PRIVATE ${SKETCH_LINK_FLAGS})
        
        # Add debug-specific linking flags if in debug mode
        if(CMAKE_BUILD_TYPE STREQUAL "DEBUG")
            target_link_options(${target_name} PRIVATE ${DEBUG_LINK_FLAGS})
        endif()
    elseif(compilation_type STREQUAL "library")
        # Library-specific linking flags (none currently, but structure is ready)
    else()
        message(FATAL_ERROR "Invalid compilation_type: ${compilation_type}. Must be 'sketch' or 'library'")
    endif()
endfunction()

message(STATUS "FastLED WASM shared build settings loaded")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  Linker: ${SELECTED_LINKER}")
message(STATUS "  FastLED source: ${FASTLED_SRC_PATH}")
if(CCACHE_EXECUTABLE)
    message(STATUS "  Ccache: enabled")
else()
    message(STATUS "  Ccache: not found")
endif() 