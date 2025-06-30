# fastled-wasm-compiler

The compiler and build system for FastLED for WASM.

[![Linting](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/lint.yml)

[![Win_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_win.yml)
[![Ubuntu_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_ubuntu.yml)
[![MacOS_Tests](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/test_macos.yml)

[![Build and Push Multi Docker Image](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml/badge.svg)](https://github.com/zackees/fastled-wasm-compiler/actions/workflows/build_multi_docker_image.yml)



```bash
# Option 1: Clone only main branch
git clone -b main --single-branch https://github.com/zackees/fastled-wasm-compiler.git

# Option 2: Clone normally then configure to exclude gh-pages
git clone https://github.com/zackees/fastled-wasm-compiler.git
cd fastled-wasm-compiler
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/* ^refs/heads/gh-pages"
```

## Development

Run `./install` to install the dependencies.

Run `./lint` to run the linter.

Run `./test` to run the tests.

# Notes:
