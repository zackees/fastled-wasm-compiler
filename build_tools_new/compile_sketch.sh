#!/bin/bash

set -e

python -m fastled_wasm_compiler.compile_sketch --sketch /examples/Blink --mode quick

