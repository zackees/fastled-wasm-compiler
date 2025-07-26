cmake_minimum_required(VERSION 3.10)
project(FastLED_Lib LANGUAGES C CXX)

# Include centralized compilation flags from TOML-generated cmake file
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake_flags.cmake)

# ========== DEBUG: TOML CENTRALIZED FLAGS VERIFICATION ==========
message(STATUS "🔍 TOML FLAGS DEBUG: Verifying centralized compilation flags are loaded correctly")
message(STATUS "📁 CMAKE_CURRENT_SOURCE_DIR = ${CMAKE_CURRENT_SOURCE_DIR}")
message(STATUS "📄 Loading flags from: ${CMAKE_CURRENT_SOURCE_DIR}/cmake_flags.cmake")

# Verify the centralized flags are loaded from build_flags.toml
list(LENGTH FASTLED_BASE_COMPILE_FLAGS BASE_COUNT)
message(STATUS "🛠️  FASTLED_BASE_COMPILE_FLAGS (${BASE_COUNT} items):")
foreach(flag ${FASTLED_BASE_COMPILE_FLAGS})
    message(STATUS "   • ${flag}")
endforeach()

list(LENGTH FASTLED_DEBUG_FLAGS DEBUG_COUNT)
message(STATUS "🐛 FASTLED_DEBUG_FLAGS (${DEBUG_COUNT} items):")
foreach(flag ${FASTLED_DEBUG_FLAGS})
    message(STATUS "   • ${flag}")
endforeach()

list(LENGTH FASTLED_QUICK_FLAGS QUICK_COUNT)
message(STATUS "⚡ FASTLED_QUICK_FLAGS (${QUICK_COUNT} items):")
foreach(flag ${FASTLED_QUICK_FLAGS})
    message(STATUS "   • ${flag}")
endforeach()

list(LENGTH FASTLED_RELEASE_FLAGS RELEASE_COUNT)
message(STATUS "🚀 FASTLED_RELEASE_FLAGS (${RELEASE_COUNT} items):")
foreach(flag ${FASTLED_RELEASE_FLAGS})
    message(STATUS "   • ${flag}")
endforeach()

# Check if flags are empty (indicates cmake_flags.cmake loading issue)
list(LENGTH FASTLED_BASE_COMPILE_FLAGS BASE_FLAGS_COUNT)
if(BASE_FLAGS_COUNT EQUAL 0)
    message(FATAL_ERROR "❌ CRITICAL: FASTLED_BASE_COMPILE_FLAGS is EMPTY! cmake_flags.cmake not loaded properly from build_flags.toml")
else()
    message(STATUS "✅ TOML FLAGS: Successfully loaded ${BASE_FLAGS_COUNT} base compilation flags")
endif()

# ——— 1) Emscripten Toolchain ——————————————————————————————————————
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

# Set linker flags globally for all link operations
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=${SELECTED_LINKER}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -fuse-ld=${SELECTED_LINKER}")
set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} -fuse-ld=${SELECTED_LINKER}")

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

# ——— 5) Base Compilation Flags ——————————————————————————————————————————
# Use centralized compilation flags from build_flags.toml
# (Generated by generate_cmake_flags.py)
add_compile_options(${FASTLED_BASE_COMPILE_FLAGS})

# Apply build mode flags globally using centralized configuration
if(CMAKE_BUILD_TYPE STREQUAL "DEBUG")
    add_compile_options(${FASTLED_DEBUG_FLAGS})
elseif(CMAKE_BUILD_TYPE STREQUAL "QUICK")
    add_compile_options(${FASTLED_QUICK_FLAGS})
elseif(CMAKE_BUILD_TYPE STREQUAL "RELEASE")
    add_compile_options(${FASTLED_RELEASE_FLAGS})
endif()

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
# Use environment variable for FastLED source path with fallback
if(DEFINED ENV{FASTLED_SRC})
    set(FASTLED_SOURCE_DIR $ENV{FASTLED_SRC})
else()
    set(FASTLED_SOURCE_DIR "/git/fastled/src")
endif()
message(STATUS "FastLED source directory: ${FASTLED_SOURCE_DIR}")

# ——— 8) Precompiled Headers (all modes) ————————————————————————————————————
# Generate precompiled headers for all build modes for faster compilation
# Create precompiled header for Arduino.h and FastLED.h

# By default, PCH is enabled. It can be disabled by setting NO_PRECOMPILED_HEADERS=1
if(NOT (DEFINED ENV{NO_PRECOMPILED_HEADERS} AND "$ENV{NO_PRECOMPILED_HEADERS}" STREQUAL "1"))
    # Always build PCH regardless of the build step
    message(STATUS "🔨 BUILDING PCH: Creating precompiled header for faster compilation")
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
else()
    message(STATUS "NO_PRECOMPILED_HEADERS=1: Precompiled headers disabled")
endif()

    message(STATUS "Creating precompiled header for ${BUILD_MODE} mode: ${PCH_HEADER}")
    message(STATUS "Precompiled header output: ${PCH_OUTPUT}")

    # ========== PCH COMPILATION WITH TOML CENTRALIZED FLAGS ==========
    message(STATUS "🔨 PCH COMPILATION: Building precompiled header with TOML centralized flags")

    # Step 1: Start with base compilation flags from build_flags.toml
    set(PCH_COMPILE_FLAGS ${FASTLED_BASE_COMPILE_FLAGS})

    list(LENGTH PCH_COMPILE_FLAGS INITIAL_PCH_COUNT)
    message(STATUS "📋 PCH Step 1: Starting with ${INITIAL_PCH_COUNT} base flags from TOML:")
    foreach(flag ${PCH_COMPILE_FLAGS})
        message(STATUS "   📌 ${flag}")
    endforeach()

    # Step 2: Add build mode specific flags from build_flags.toml
    message(STATUS "🎯 PCH Step 2: Adding ${CMAKE_BUILD_TYPE} mode flags from TOML")
    if(CMAKE_BUILD_TYPE STREQUAL "DEBUG")
        list(APPEND PCH_COMPILE_FLAGS ${FASTLED_DEBUG_FLAGS})
        message(STATUS "   ✅ Added ${DEBUG_COUNT} DEBUG mode flags")
    elseif(CMAKE_BUILD_TYPE STREQUAL "QUICK")
        list(APPEND PCH_COMPILE_FLAGS ${FASTLED_QUICK_FLAGS})
        message(STATUS "   ✅ Added ${QUICK_COUNT} QUICK mode flags")
    elseif(CMAKE_BUILD_TYPE STREQUAL "RELEASE")
        list(APPEND PCH_COMPILE_FLAGS ${FASTLED_RELEASE_FLAGS})
        message(STATUS "   ✅ Added ${RELEASE_COUNT} RELEASE mode flags")
    else()
        message(WARNING "⚠️  Unknown CMAKE_BUILD_TYPE: ${CMAKE_BUILD_TYPE}")
    endif()

    list(LENGTH PCH_COMPILE_FLAGS AFTER_BUILD_MODE_COUNT)
    message(STATUS "📊 PCH Step 2 Result: Now have ${AFTER_BUILD_MODE_COUNT} total flags")

    # Step 3: Filter out flags that are incompatible with PCH compilation
    message(STATUS "🔍 PCH Step 3: Filtering out PCH-incompatible flags")
    set(PCH_FILTERED_FLAGS "")
    set(FILTERED_OUT_FLAGS "")

    foreach(flag ${PCH_COMPILE_FLAGS})
        # Only remove flags that actually cause PCH compilation issues
        # Keep ALL build mode flags (-flto=thin, -gsource-map, -ffile-prefix-map) for consistency
        if(flag STREQUAL "-emit-llvm" OR flag STREQUAL "-Wall")
            list(APPEND FILTERED_OUT_FLAGS ${flag})
            message(STATUS "   ❌ Filtered out: ${flag} (PCH incompatible)")
        else()
            list(APPEND PCH_FILTERED_FLAGS ${flag})
        endif()
    endforeach()

    list(LENGTH PCH_FILTERED_FLAGS FINAL_COUNT)
    list(LENGTH FILTERED_OUT_FLAGS FILTERED_COUNT)
    message(STATUS "📊 PCH Step 3 Result: ${FINAL_COUNT} flags kept, ${FILTERED_COUNT} flags filtered out")

    # Step 4: Convert list to space-separated string for proper command line expansion
    list(JOIN PCH_FILTERED_FLAGS " " PCH_FLAGS_STRING)

    message(STATUS "🚀 PCH FINAL FLAGS STRING: ${PCH_FLAGS_STRING}")
    if(PCH_FLAGS_STRING STREQUAL "")
        message(FATAL_ERROR "❌ CRITICAL: PCH_FLAGS_STRING is EMPTY! All TOML flags were lost during processing")
    endif()

    # ========== PCH FINAL VERIFICATION ==========
    message(STATUS "✅ PCH COMPILATION READY: Using TOML centralized flags for ${BUILD_MODE} mode")
    message(STATUS "📝 Final PCH compilation flags (${FINAL_COUNT} total):")
    foreach(flag ${PCH_FILTERED_FLAGS})
        message(STATUS "   🔧 ${flag}")
    endforeach()

    # Use a shell script approach to properly handle flag expansion
    set(PCH_COMPILE_SCRIPT "${ABS_BUILD_OUTPUT_DIR}/compile_pch.sh")
    file(WRITE ${PCH_COMPILE_SCRIPT} 
"#!/bin/bash
set -e
echo \"Building PCH with flags: ${PCH_FLAGS_STRING}\"
${CMAKE_CXX_COMPILER_LAUNCHER} ${CMAKE_CXX_COMPILER} ${PCH_FLAGS_STRING} -I${FASTLED_SOURCE_DIR} -I${FASTLED_SOURCE_DIR}/platforms/wasm/compiler -I. -Isrc -x c++-header ${PCH_HEADER} -o ${PCH_OUTPUT}")

    # Make script executable
    file(CHMOD ${PCH_COMPILE_SCRIPT} 
         PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE 
                     GROUP_READ GROUP_EXECUTE 
                     WORLD_READ WORLD_EXECUTE)

    # Automatically find all FastLED header files for proper dependency tracking
    file(GLOB_RECURSE FASTLED_HEADERS "${FASTLED_SOURCE_DIR}/*.h*")
    
    # Create a target for the precompiled header with proper dependency tracking
    add_custom_target(fastled_pch ALL
      COMMAND ${PCH_COMPILE_SCRIPT}
      DEPENDS ${PCH_HEADER} ${FASTLED_HEADERS}
      COMMENT "Building precompiled header fastled_pch.h.gch for ${BUILD_MODE} mode with centralized flags"
      VERBATIM
      BYPRODUCTS ${PCH_OUTPUT}
    )
    
    # Create a dummy target for dependency consistency
    add_custom_target(fastled_pch_dummy)

# ——— 9) Add FastLED Library ———————————————————————————————————————
add_subdirectory(${FASTLED_SOURCE_DIR} ${CMAKE_BINARY_DIR}/fastled)

# Make FastLED library depend on precompiled header (all modes)
if(NOT (DEFINED ENV{NO_PRECOMPILED_HEADERS} AND "$ENV{NO_PRECOMPILED_HEADERS}" STREQUAL "1"))
    add_dependencies(fastled fastled_pch)
endif()

# ——— 10) Control Library Name Based on Archive Mode ——————————————————————
# Check for archive build mode
if(DEFINED ENV{ARCHIVE_BUILD_MODE})
    string(TOLOWER "$ENV{ARCHIVE_BUILD_MODE}" ARCHIVE_MODE)
    if(ARCHIVE_MODE STREQUAL "thin")
        message(STATUS "EXCLUSIVE MODE: Building ONLY thin archives")
        set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled-thin")
    elseif(ARCHIVE_MODE STREQUAL "regular")
        message(STATUS "EXCLUSIVE MODE: Building ONLY regular archives")
        set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled")
    else()
        set(ARCHIVE_MODE "both")
        message(STATUS "DUAL MODE: Building both archive types (current)")
        # Current logic based on NO_THIN_LTO
        if(DEFINED ENV{NO_THIN_LTO} AND "$ENV{NO_THIN_LTO}" STREQUAL "1")
            message(STATUS "NO_THIN_LTO=1: Building libfastled.a")
            set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled")
        else()
            message(STATUS "NO_THIN_LTO=0: Building libfastled-thin.a")
            set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled-thin")
        endif()
    endif()
else()
    # Default to "regular" mode for best performance
    set(ARCHIVE_MODE "regular")
    message(STATUS "REGULAR MODE: Building regular archives only (default)")
    set_target_properties(fastled PROPERTIES OUTPUT_NAME "fastled")
endif()
