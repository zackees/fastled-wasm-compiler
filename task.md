# TASK: Fix Docker Image — Missing JS Files in Output + Broken Server Entry Point

## Problem Summary

The `niteris/fastled-wasm:latest` Docker image has two critical issues:

1. **Vite dist JS files are not making it into the compilation output zip** — only `.js.map` files appear, but the actual `.js`, `.html`, `.css` bundles are missing
2. **The `/js/run.py` server entry point is missing** — the `fastled-wasm` client can't start the Docker container as a compile server

## Issue 1: Missing JS Bundles in Output

### What's happening

The Vite `dist/` directory inside the container **is correct** — it contains all expected files:

```
/git/fastled/src/platforms/wasm/compiler/dist/
├── audio_worklet_processor.js           (4 KB)
├── fastled_background_worker.js         (26 KB) ← has the ./fastled.js fix
├── fastled_background_worker.js.map     (54 KB)
├── index.css                            (48 KB)
├── index.html                           (9 KB)
├── index.js                             (1.8 MB)
├── index.js.map                         (3.3 MB)
└── assets/
    ├── three.module-*.js                (code-split chunks)
    ├── graphics_manager-*.js
    └── *.js.map
```

But the **output sent back to the client** only contains:

```
fastled_js/
├── fastled.js                           ✅ (from build dir)
├── fastled.js.symbols                   ✅ (from build dir)
├── fastled.wasm                         ✅ (from build dir)
├── fastled_background_worker.js.map     ✅ (from dist)
├── index.js.map                         ✅ (from dist)
├── assets/*.js.map                      ✅ (from dist)
├── files.json                           ✅
├── hash.txt                             ✅
├── out.txt                              ✅
├── perf.txt                             ✅
├── fastled_background_worker.js         ❌ MISSING
├── index.html                           ❌ MISSING
├── index.js                             ❌ MISSING
├── index.css                            ❌ MISSING
├── audio_worklet_processor.js           ❌ MISSING
└── assets/*.js                          ❌ MISSING (only .js.map present)
```

### Where to investigate

The copy logic is in `src/fastled_wasm_compiler/copy_files_and_output_manifest.py` lines 103-119:

```python
# Copy Vite build output from dist/
dist_dir = assets_dir / "dist"
print(f"Copying Vite build output from {dist_dir} to {out_dir}")
for item in dist_dir.iterdir():
    dest = out_dir / item.name
    if item.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(item, dest)
    else:
        shutil.copy2(item, dest)
```

This code looks correct — it iterates `dist_dir` and copies everything. But only `.js.map` files end up in the output. Possible causes:

1. **The zip creation step is filtering out `.js` files** — check how the output directory gets zipped and sent back. Maybe there's a filter that excludes `.js` to avoid sending source files, but it's now accidentally excluding the bundled output too.
2. **A cleanup step runs after copying** that removes `.js` files (maybe `fastled.*` glob matching is too broad)
3. **The `dist/` directory at runtime differs from build time** — maybe `ensure_vite_built()` is rebuilding with wrong config or the dist gets cleared somehow
4. **File permissions** — the Dockerfile sets files to read-only (`chmod -R a-w`), which shouldn't prevent copying but might cause issues

### How to reproduce

```bash
# From fastled-wasm repo:
cd ~/dev/fastled-wasm/tests/unit/test_ino/wasm
rm -rf fastled_js
uv run fastled --just-compile
ls fastled_js/
# Observe: no index.html, no index.js, no fastled_background_worker.js
```

## Issue 2: Missing `/js/run.py` Server Entry Point

### What's happening

The `fastled-wasm` client starts the Docker container with:

```python
# compile_server_impl.py line 289
server_command = ["python", "/js/run.py", "server"] + SERVER_OPTIONS
```

But `/js/run.py` does not exist in the current Docker image. The only thing at `/js/` is `/js/src/`.

This causes the container to fail to start as a compile server, which is why:
- `CompileServer(auto_start=True)` fails with "Server did not start"
- The client falls back to the web compiler at `fastled.onrender.com`

### What needs to happen

Either:
- **Option A**: Add `run.py` back to the Docker image (it was part of the old FastLED repo at `/js/run.py`)
- **Option B**: Update the `fastled-wasm` client to use the new entry point (`fastled-wasm-compiler` CLI with appropriate server flags)

The `run.py` likely lived in the FastLED main repo and got copied to `/js/` during Docker build. Check the old Dockerfile history or the FastLED main repo for this file.

## Verification

After fixing both issues, from the `fastled-wasm` repo:

```bash
# 1. Rebuild Docker image
cd ~/dev/fastled-wasm-compiler
docker build -t niteris/fastled-wasm:latest .
docker push niteris/fastled-wasm:latest

# 2. Purge old containers and test
cd ~/dev/fastled-wasm
uv run fastled --purge
cd tests/unit/test_ino/wasm
rm -rf fastled_js
uv run fastled --just-compile

# 3. Verify all files present
ls fastled_js/
# Must have: index.html, index.js, index.css, fastled_background_worker.js,
#            audio_worklet_processor.js, assets/*.js

# 4. Verify URL fix in worker
grep 'new URL(' fastled_js/fastled_background_worker.js
# Must show: ./fastled.js (NOT ../../fastled.js)

# 5. Run unit tests
cd ~/dev/fastled-wasm
bash test
```
