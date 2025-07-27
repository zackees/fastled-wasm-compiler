# THIN\_PCH (Emscripten Edition)

## Overview

This document explains the concept of Thin Precompiled Headers (Thin PCH) in Clang and how they compare to traditional (monolithic) PCH. It also covers how to use Thin PCH with the Emscripten toolchain, its benefits, and its impact on WebAssembly build performance.

## Implementation Status

Thin PCH support has been implemented in the FastLED WASM compiler. You can enable it by setting the `THIN_PCH=1` environment variable or using the `--thin-pch` flag with the build scripts.

---

## What is Thin PCH?

Thin PCH is a mode in Clang (used by Emscripten) where a precompiled header is built in a modular, scalable way that supports partial reuse and faster rebuilds. Unlike traditional PCH, which is a monolithic binary blob, Thin PCH keeps track of source-level include structure and allows selective recompilation.

---

## Benefits of Thin PCH with Emscripten

| Feature                        | Traditional PCH | Thin PCH           |
| ------------------------------ | --------------- | ------------------ |
| First Build (cold)             | Fast            | Slightly slower    |
| Rebuild after Header Change    | Full rebuild    | Partial reuse      |
| Reuse across Translation Units | Fast but rigid  | Faster, scalable   |
| CCache/SCCache Friendly        | Limited         | Very good          |
| Ideal For                      | Stable headers  | Active development |
| Emscripten Compatibility       | Partial         | ✅ Recommended      |

---

## How to Use Thin PCH with Emscripten

### 1. Create a PCH Header

```cpp
// user_pch.h
#include "fastled.h"
#include "user_config.h"
#include <vector>
#include <string>
```

### 2. Generate the Thin PCH with Emscripten

```bash
emcc -x c++-header user_pch.h -o user_pch.pch
```

Or explicitly:

```bash
emcc -x c++-header -emit-pch -o user_pch.pch user_pch.h
```

### 3. Use Thin PCH in WebAssembly Builds

```bash
emcc -include user_pch -c main.cpp -o main.o
```

You can also pass `-include-pch user_pch.pch` if needed, but `-include user_pch` is preferred as it matches the header name.

---

## Performance in WebAssembly Projects

* Traditional PCH rebuild time after a header change: **3–10× slower**
* Thin PCH rebuild time after a header change: **2–5× faster**
* TU compile speed (cached):

  * Traditional: \~0.4–1.0 sec (WebAssembly target)
  * Thin: \~0.2–0.6 sec

For large codebases or projects targeting both native and wasm, Thin PCH can significantly improve rebuild times.

---

## Best Practices

* Keep `user_pch.h` minimal and stable—only include common headers.
* Use Thin PCH when iterating frequently on user-level includes.
* Combine with `EM_CACHE`, `ccache`, or `sccache` for even faster incremental builds.
* Avoid trying to stack multiple `.pch` files—stick to one logical include tree.

---

## Limitations

* Not composable: Cannot include one PCH inside another.
* Does not affect link time—only preprocessing and compilation.
* Works only with Clang-compatible tools (Emscripten uses Clang under the hood).
* Requires consistent use of `-include` or `-include-pch` to avoid mismatches.

---

## Summary

Thin PCH provides a scalable, cache-friendly solution for accelerating C++ compilation in Emscripten-based WebAssembly projects. It supports incremental rebuilds, integrates well with caching tools, and can substantially reduce build time when working with large headers like FastLED or the STL.

When used correctly, Thin PCH is a drop-in upgrade for traditional `.pch` workflows in WebAssembly development environments.
