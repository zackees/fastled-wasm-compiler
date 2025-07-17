cmake_minimum_required(VERSION 3.10)
project(FastLED_Lib LANGUAGES C CXX)

# ——— 1) Toolchain & Archiver ——————————————————————————————————————
set(CMAKE_C_COMPILER   "emcc")
set(CMAKE_CXX_COMPILER "em++")
set(CMAKE_AR           "emar")
set(CMAKE_RANLIB       "emranlib")

# (optional) use ccache for faster rebuilds
set(CMAKE_C_COMPILER_LAUNCHER   "ccache")
set(CMAKE_CXX_COMPILER_LAUNCHER "ccache")

# ——— 2) Build Mode —————————————————————————————————————————————
if(NOT DEFINED ENV{BUILD_MODE})
  set(BUILD_MODE "QUICK")
else()
  set(BUILD_MODE $ENV{BUILD_MODE})
endif()
string(TOUPPER "${BUILD_MODE}" BUILD_MODE)
set(CMAKE_BUILD_TYPE "${BUILD_MODE}" CACHE STRING "" FORCE)
message(STATUS "Build mode: ${CMAKE_BUILD_TYPE}")

# ——— 3) Linker Selection ———————————————————————————————————————————
# Check for LINKER environment variable first
if(DEFINED ENV{LINKER})
  set(SELECTED_LINKER $ENV{LINKER})
  message(STATUS "Using linker from LINKER environment variable: ${SELECTED_LINKER}")
else()
  # Auto-detect linker (same logic as FastLED CMakeLists.txt)
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

# Set linker flags for the selected linker
set(LINKER_FLAGS "-fuse-ld=${SELECTED_LINKER}")
message(STATUS "Using linker flags: ${LINKER_FLAGS}")

# Set linker flags globally for all link operations
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${LINKER_FLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${LINKER_FLAGS}")
set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} ${LINKER_FLAGS}")

# ——— 4) Compiler Standards ———————————————————————————————————————
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Control thin LTO via environment variable
if(DEFINED ENV{NO_THIN_LTO} AND "$ENV{NO_THIN_LTO}" STREQUAL "1")
  set(NO_THIN_LTO ON)
  message(STATUS "NO_THIN_LTO=1: Thin LTO disabled")
else()
  set(NO_THIN_LTO OFF)
  message(STATUS "NO_THIN_LTO=0: Thin LTO enabled")
endif()

# ——— FASTLED_ALL_SRC (Unified Compilation) ——————————————————————
# Always build in unified compilation mode.
message(STATUS "FASTLED_ALL_SRC enabled: using unified compilation for FastLED")
set(FASTLED_ALL_SRC 1 CACHE BOOL "Enable unified FastLED compilation" FORCE)
# Ensure all translation units see the definition
add_compile_definitions(FASTLED_ALL_SRC=1)

# ——— 5) Compiler Flags ——————————————————————————————————————————
set(SHARED_FLAGS
  ${LINKER_FLAGS}  # Add linker flags to all builds
  -emit-llvm  # Generate LLVM bitcode instead of object files for faster builds
  -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50
  -DFASTLED_FORCE_NAMESPACE=1
  -DFASTLED_USE_PROGMEM=0
  -DUSE_OFFSET_CONVERTER=0
  -DGL_ENABLE_GET_PROC_ADDRESS=0
  -fpermissive
  -Wno-constant-logical-operand
  -Wnon-c-typedef-for-linkage
  -Werror=bad-function-cast
  -Werror=cast-function-type
  # Threading disabled flags
  -fno-threadsafe-statics  # Disable thread-safe static initialization
  -DEMSCRIPTEN_NO_THREADS  # Define to disable threading
  -D_REENTRANT=0  # Disable reentrant code
)

set(CXX_ONLY_FLAGS
  -std=gnu++17
)

if(BUILD_MODE STREQUAL "DEBUG")
  list(APPEND SHARED_FLAGS
    -g3
    -gsource-map
    -ffile-prefix-map=/=sketchsource/
    -fsanitize=address
    -fsanitize=undefined
    -fno-inline
    -O0
  )
elseif(BUILD_MODE STREQUAL "QUICK")
  list(APPEND SHARED_FLAGS
    -flto=thin
    -O0
    -sASSERTIONS=0
    -g0
    -fno-inline-functions
    -fno-vectorize
    -fno-unroll-loops
    -fno-strict-aliasing
  )
else()  # RELEASE
  list(APPEND SHARED_FLAGS
    -Oz
  )
endif()

add_compile_options(${SHARED_FLAGS})
add_compile_options($<$<COMPILE_LANGUAGE:CXX>:${CXX_ONLY_FLAGS}>)

# ——— 6) Output Directory (absolute) ——————————————————————————————
string(TOLOWER "${BUILD_MODE}" BUILD_MODE_LOWER)
# Use environment variable for build root with fallback
if(DEFINED ENV{ENV_BUILD_ROOT})
  set(BUILD_ROOT_BASE $ENV{ENV_BUILD_ROOT})
else()
  set(BUILD_ROOT_BASE "/build")
endif()
set(ABS_BUILD_OUTPUT_DIR "${BUILD_ROOT_BASE}/${BUILD_MODE_LOWER}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${ABS_BUILD_OUTPUT_DIR}" CACHE PATH "" FORCE)
message(STATUS "Archive output directory: ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY}")

# ——— 7) FastLED Source Directory Setup ———————————————————————————————————————
# Use environment variable for FastLED source directory with fallback
if(DEFINED ENV{ENV_FASTLED_SOURCE_PATH})
  set(FASTLED_SOURCE_DIR $ENV{ENV_FASTLED_SOURCE_PATH})
elseif(DEFINED ENV{ENV_FASTLED_ROOT})
  set(FASTLED_SOURCE_DIR "$ENV{ENV_FASTLED_ROOT}/src")
else()
  set(FASTLED_SOURCE_DIR "/git/fastled/src")
endif()
message(STATUS "FastLED source directory: ${FASTLED_SOURCE_DIR}")

# ——— 8) Precompiled Headers (all modes) ————————————————————————————————————
# Generate precompiled headers for all build modes for faster compilation
# Create precompiled header for Arduino.h and FastLED.h
set(PCH_HEADER "${ABS_BUILD_OUTPUT_DIR}/fastled_pch.h")
set(PCH_OUTPUT "${ABS_BUILD_OUTPUT_DIR}/fastled_pch.h.gch")

# Create the precompiled header source file
file(WRITE ${PCH_HEADER} 
"#pragma once
// Precompiled header for FastLED WASM compilation
// This includes the most commonly used headers to speed up compilation

#include <Arduino.h>
#include <FastLED.h>
")

message(STATUS "Creating precompiled header for ${BUILD_MODE} mode: ${PCH_HEADER}")
message(STATUS "Precompiled header output: ${PCH_OUTPUT}")

# Create PCH-specific flags (exclude -emit-llvm which doesn't work with precompiled headers)
set(PCH_FLAGS ${SHARED_FLAGS})
list(REMOVE_ITEM PCH_FLAGS "-emit-llvm")

# Build the precompiled header using emcc with modified flags
add_custom_command(
  OUTPUT ${PCH_OUTPUT}
  COMMAND ${CMAKE_CXX_COMPILER} 
          ${PCH_FLAGS} 
          ${CXX_ONLY_FLAGS}
          -I${FASTLED_SOURCE_DIR}
          -I${FASTLED_SOURCE_DIR}/platforms/wasm/compiler
          -I.
          -Isrc
          -x c++-header 
          ${PCH_HEADER} 
          -o ${PCH_OUTPUT}
  DEPENDS ${PCH_HEADER}
  COMMENT "Building precompiled header fastled_pch.h.gch for ${BUILD_MODE} mode with matching optimization"
  VERBATIM
)

# Create a target for the precompiled header
add_custom_target(fastled_pch ALL DEPENDS ${PCH_OUTPUT})

# ——— 9) Add FastLED Library ———————————————————————————————————————
add_subdirectory(${FASTLED_SOURCE_DIR} ${CMAKE_BINARY_DIR}/fastled)

# Make FastLED library depend on precompiled header (all modes)
add_dependencies(fastled fastled_pch)

# ——— 10) Control Library Name Based on NO_THIN_LTO ——————————————————————
if(DEFINED ENV{NO_THIN_LTO} AND "$ENV{NO_THIN_LTO}" STREQUAL "1")
  message(STATUS "NO_THIN_LTO=1: Building libfastled.a")
  set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled")
else()
  message(STATUS "NO_THIN_LTO=0: Building libfastled-thin.a")
  set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled-thin")
endif()
