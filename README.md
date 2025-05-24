# fastled-wasm-compiler

The compiler and build system for FastLED for WASM.

[![Linting](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml)

[![Win_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml)
[![Ubuntu_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml)
[![MacOS_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml)

[![Build and Push Multi Docker Image](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml)


## Development

Run `./install` to install the dependencies.

Run `./lint` to run the linter.

Run `./test` to run the tests.

# Notes:

### Compiler settings for debug

```
.39 #########################
7.39 # C++/C Compiler Flags: #
7.39 #########################
7.39
7.39 CC/CXX flags:
7.39   -DFASTLED_ENGINE_EVENTS_MAX_LISTENERS=50
7.39   -DFASTLED_FORCE_NAMESPACE=1
7.39   -DFASTLED_USE_PROGMEM=0
7.39   -DUSE_OFFSET_CONVERTER=0
7.39   -std=gnu++17
7.39   -fpermissive
7.39   -Wno-constant-logical-operand
7.39   -Wnon-c-typedef-for-linkage
7.39   -Werror=bad-function-cast
7.39   -Werror=cast-function-type
7.39   -sERROR_ON_WASM_CHANGES_AFTER_LINK
7.39   -I
7.39   src
7.39   -I/js/fastled/src/platforms/wasm/compiler
7.39   -g3
7.39   -O0
7.39   -gsource-map
7.39   -ffile-prefix-map=/=dwarfsource/
7.39   -fsanitize=address
7.39   -fsanitize=undefined
7.39   -fno-inline
7.39   -O0
7.39 FastLED Library CC flags:
7.39   -Werror=bad-function-cast
7.39   -Werror=cast-function-type
7.39   -I/js/fastled/src/platforms/wasm/compiler
7.39   -g3
7.39   -O0
7.39   -gsource-map
7.39   -ffile-prefix-map=/=dwarfsource/
7.39   -fsanitize=address
7.39   -fsanitize=undefined
7.39   -fno-inline
7.39   -O0
7.39 Sketch CC flags:
7.39
7.39 #################
7.39 # Linker Flags: #
7.39 #################
7.39
7.39   --bind
7.39   -fuse-ld=lld
7.39   -sWASM=1
7.39   -sALLOW_MEMORY_GROWTH=1
7.39   -sINITIAL_MEMORY=134217728
7.39   -sEXPORTED_RUNTIME_METHODS=['ccall','cwrap','stringToUTF8','lengthBytesUTF8']
7.39   -sEXPORTED_FUNCTIONS=['_malloc','_free','_extern_setup','_extern_loop','_fastled_declare_files']
7.39   --no-entry
7.39   --emit-symbol-map
7.39   -gseparate-dwarf=/js/.pio/build/wasm-debug/fastled.wasm.dwarf
7.39   -sSEPARATE_DWARF_URL=fastled.wasm.dwarf
7.39   -sSTACK_OVERFLOW_CHECK=2
7.39   -sASSERTIONS=1
7.39   -fsanitize=address
7.39   -fsanitize=undefined
7.39   -sMODULARIZE=1
7.39   -sEXPORT_NAME=fastled
7.39   -o
7.39   /js/.pio/build/wasm-debug/fastled.js
7.39   --source-map-base=http://localhost:8000/
7.39
7.39 ##########################
7.39 # FastLED Library Flags: #
7.39 ##########################
7.39
7.39   --bind
7.39   -Wl,--whole-archive,-fuse-ld=lld
7.39   -Werror=bad-function-cast
7.39   -Werror=cast-function-type
7.39   --emit-symbol-map
7.39   -gseparate-dwarf=/js/.pio/build/wasm-debug/fastled.wasm.dwarf
7.39   -sSEPARATE_DWARF_URL=fastled.wasm.dwarf
7.39   -sSTACK_OVERFLOW_CHECK=2
7.39   -sASSERTIONS=1
7.39   -fsanitize=address
7.39   -fsanitize=undefined
7.39
```