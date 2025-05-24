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

# ——— 3) Compiler Standards ———————————————————————————————————————
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ——— 4) Compiler Flags ——————————————————————————————————————————
set(SHARED_FLAGS
  -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50
  -DFASTLED_FORCE_NAMESPACE=1
  -DFASTLED_USE_PROGMEM=0
  -DUSE_OFFSET_CONVERTER=0
  -fpermissive
  -Wno-constant-logical-operand
  -Wnon-c-typedef-for-linkage
  -Werror=bad-function-cast
  -Werror=cast-function-type
)

set(CXX_ONLY_FLAGS
  -std=gnu++17
)

if(BUILD_MODE STREQUAL "DEBUG")
  list(APPEND SHARED_FLAGS
    -g3
    -Og
    -fno-inline
    -fno-strict-aliasing
    -fno-inline-functions
    -fno-unroll-loops
    -fno-vectorize
    -fsanitize=address
    -fsanitize=undefined
    -gsource-map
    -ffile-prefix-map=/=dwarfsource/

  )
elseif(BUILD_MODE STREQUAL "QUICK")
  list(APPEND SHARED_FLAGS
    -O1
    -fno-inline
    -fno-strict-aliasing
    -fno-inline-functions
    -fno-unroll-loops
    -fno-vectorize
  )
else()  # RELEASE
  list(APPEND SHARED_FLAGS
    -Oz
  )
endif()

add_compile_options(${SHARED_FLAGS})
add_compile_options($<$<COMPILE_LANGUAGE:CXX>:${CXX_ONLY_FLAGS}>)

# ——— 5) Output Directory (absolute) ——————————————————————————————
string(TOLOWER "${BUILD_MODE}" BUILD_MODE_LOWER)
set(ABS_BUILD_OUTPUT_DIR "/build/${BUILD_MODE_LOWER}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${ABS_BUILD_OUTPUT_DIR}" CACHE PATH "" FORCE)
message(STATUS "Archive output directory: ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY}")

# ——— 6) Add FastLED Library ———————————————————————————————————————
set(FASTLED_SOURCE_DIR "/git/fastled/src")
message(STATUS "FastLED source directory: ${FASTLED_SOURCE_DIR}")
add_subdirectory(${FASTLED_SOURCE_DIR} ${CMAKE_BINARY_DIR}/fastled)
