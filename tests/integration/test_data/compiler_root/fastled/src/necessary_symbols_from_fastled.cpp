/// Special dependencies because we don't have the full led source code.

#include <emscripten.h>
#include <string>

EMSCRIPTEN_KEEPALIVE extern "C" int extern_setup() { return 0; }
EMSCRIPTEN_KEEPALIVE extern "C" int extern_loop() { return 0; }
EMSCRIPTEN_KEEPALIVE extern "C" void fastled_declare_files(std::string jsonStr) {}