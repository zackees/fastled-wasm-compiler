#include <emscripten.h>

EMSCRIPTEN_KEEPALIVE extern "C" int extern_setup() { return 0; }
EMSCRIPTEN_KEEPALIVE extern "C" int extern_loop() { return 0; }

EMSCRIPTEN_KEEPALIVE void fastled_declare_files(std::string jsonStr) {}