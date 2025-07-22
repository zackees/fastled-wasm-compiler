# FastLED WASM Shared Build Settings
# This file contains compilation settings shared between sketch and library builds
# while keeping linking settings separate.
#
# IMPORTANT: This file now uses the centralized TOML build flags system.
# All compilation flags are loaded from build_flags.toml via cmake_flags.cmake

cmake_minimum_required(VERSION 3.10)

# ================================================================================================
# CENTRALIZED FLAGS LOADING
# ================================================================================================

# Load centralized compilation flags from TOML-generated cmake file
# This ensures consistency with the main build system
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake_flags.cmake)

# Verify the centralized flags are loaded
list(LENGTH FASTLED_BASE_COMPILE_FLAGS BASE_FLAGS_COUNT)
if(BASE_FLAGS_COUNT EQUAL 0)
    message(FATAL_ERROR "❌ CRITICAL: FASTLED_BASE_COMPILE_FLAGS is EMPTY! cmake_flags.cmake not loaded properly from build_flags.toml")
else()
    message(STATUS "✅ Shared Build Settings: Successfully loaded ${BASE_FLAGS_COUNT} centralized flags from TOML")
endif()

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
# CENTRALIZED COMPILATION FLAGS (FROM TOML)
# ================================================================================================

# Base compilation flags are now loaded from centralized TOML system
# FASTLED_BASE_COMPILE_FLAGS contains: base defines + base compiler flags + library flags
# This replaces the old hardcoded SHARED_DEFINES and SHARED_COMPILER_FLAGS

# Base include directories (still defined here as they're path-dependent)
set(SHARED_INCLUDE_DIRS
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${FASTLED_SRC_PATH}
    ${FASTLED_SRC_PATH}/platforms/wasm/compiler
)

# ================================================================================================
# SKETCH-SPECIFIC FLAGS (FROM TOML)
# ================================================================================================

# Sketch-specific flags are extracted from the centralized system
# Note: These are currently embedded in FASTLED_BASE_COMPILE_FLAGS
# If needed, they can be separated in the TOML structure

set(SKETCH_DEFINES
    -DSKETCH_COMPILE=1
    -DFASTLED_WASM_USE_CCALL
)

set(SKETCH_COMPILER_FLAGS
    # Additional sketch-specific compiler flags (if any)
)

# ================================================================================================
# LIBRARY-SPECIFIC FLAGS (FROM TOML)
# ================================================================================================

# Library-specific flags are extracted from the centralized system
# Note: These are currently embedded in FASTLED_BASE_COMPILE_FLAGS
set(LIBRARY_DEFINES
    # Library-specific defines (if any)
)

set(LIBRARY_COMPILER_FLAGS
    # Library-specific flags are in FASTLED_BASE_COMPILE_FLAGS from TOML
)

# ================================================================================================
# BUILD MODE FLAGS (FROM TOML)
# ================================================================================================

# Build mode flags are now loaded from centralized TOML system
# FASTLED_DEBUG_FLAGS, FASTLED_QUICK_FLAGS, FASTLED_RELEASE_FLAGS are available

# ================================================================================================
# BASE LINKING FLAGS (SHARED)
# ================================================================================================

set(SHARED_LINK_FLAGS
    -fuse-ld=${SELECTED_LINKER}
    -sWASM=1
    # Threading enabled for socket emulation (but no proxy to pthread)
    -pthread
    -sUSE_PTHREADS=1
    -lwebsocket.js
    -sPROXY_POSIX_SOCKETS=1
)

# ================================================================================================
# SKETCH-SPECIFIC LINKING FLAGS (FROM TOML)
# ================================================================================================

set(SKETCH_LINK_FLAGS
    --no-entry
    --emit-symbol-map
    -sMODULARIZE=1
    -sEXPORT_NAME=fastled
    -sALLOW_MEMORY_GROWTH=1
    -sINITIAL_MEMORY=134217728  # 128 MB
    -sAUTO_NATIVE_LIBRARIES=0
    "-sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','UTF8ToString','lengthBytesUTF8','HEAPU8','getValue']"
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files','_getStripPixelData','_getFrameData','_freeFrameData']"
    -sEXIT_RUNTIME=0
    -sFILESYSTEM=0
    -Wl,--gc-sections
    --source-map-base=http://localhost:8000/
    # Asyncify support for async/await style coding with delay() functions
    -sASYNCIFY=1
    -sASYNCIFY_STACK_SIZE=10485760  # 10MB stack for asyncify operations
    "-sASYNCIFY_EXPORTS=['_extern_setup','_extern_loop']"  # Allow main FastLED functions to be async
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
# HELPER FUNCTIONS (UPDATED TO USE CENTRALIZED FLAGS)
# ================================================================================================

# Function to apply shared compilation flags to a target
function(apply_shared_compilation_flags target_name compilation_type)
    # Apply centralized compilation flags from TOML system
    target_compile_options(${target_name} PRIVATE ${FASTLED_BASE_COMPILE_FLAGS})
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
    
    # Apply build mode flags from centralized TOML system
    if(CMAKE_BUILD_TYPE STREQUAL "DEBUG")
        target_compile_options(${target_name} PRIVATE ${FASTLED_DEBUG_FLAGS})
    elseif(CMAKE_BUILD_TYPE STREQUAL "QUICK")
        target_compile_options(${target_name} PRIVATE ${FASTLED_QUICK_FLAGS})
    elseif(CMAKE_BUILD_TYPE STREQUAL "RELEASE")
        target_compile_options(${target_name} PRIVATE ${FASTLED_RELEASE_FLAGS})
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

message(STATUS "FastLED WASM shared build settings loaded (using centralized TOML flags)")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  Linker: ${SELECTED_LINKER}")
message(STATUS "  FastLED source: ${FASTLED_SRC_PATH}")
message(STATUS "  Centralized flags: ${BASE_FLAGS_COUNT} items from build_flags.toml")
if(CCACHE_EXECUTABLE)
    message(STATUS "  Ccache: enabled")
else()
    message(STATUS "  Ccache: not found")
endif() 