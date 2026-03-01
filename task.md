# TASK: Fix Vite Worker URL Paths + Rebuild Docker Image

## URGENT: Fix `download_fastled.sh` file extension whitelist

**Status:** MUST FIX before Docker rebuild.

The file `build_tools/download_fastled.sh` has a `find` command (around line 25)
that deletes all files not matching a whitelisted set of extensions. The whitelist
is missing extensions required by the Vite TypeScript build:

| Missing ext | Required by |
|-------------|-------------|
| `.ts`       | TypeScript source files (`fastled_background_worker.ts`, `index.ts`, etc.) |
| `.mts`      | TypeScript config (`vite.config.mts`) |
| `.json`     | `package.json`, `tsconfig.json`, `package-lock.json` |
| `.ttf`      | Font files (`RobotoCondensed-Light.ttf`) |

Without these, the Vite build at Dockerfile line 156 (`npm install && npx vite build`)
will fail because `package.json`, `vite.config.mts`, and all `.ts` source files
are deleted before the build runs.

**Fix:** Add the missing extensions to the `find` whitelist in `build_tools/download_fastled.sh`:

```bash
find . -type f ! \( \
  -name "*.cpp"  -o \
  -name "*.hpp"  -o \
  -name "*.h"    -o \
  -name "*.c"    -o \
  -name "*.sh"   -o \
  -name "*.js"   -o \
  -name "*.mjs"  -o \
  -name "*.css"  -o \
  -name "*.txt"  -o \
  -name "*.html" -o \
  -name "*.toml" -o \
  -name "*.ts"   -o \
  -name "*.mts"  -o \
  -name "*.json" -o \
  -name "*.ttf"  \
\) -delete
```

## URGENT: Vite worker URL path regression

**Status:** Fixed in FastLED main repo, needs Docker rebuild to pick up.

The FastLED main repo fixed a Vite migration regression in
`src/platforms/wasm/compiler/modules/core/fastled_background_worker.ts`.
After Vite bundling, the background worker is output at root level alongside
`fastled.js` and `fastled.wasm`. Three relative URLs used `../../` (correct
for the pre-bundle source location at `modules/core/`) but wrong after bundling.

**Changed from `../../` to `./`:**
1. `fastledScriptPath` — fetches `fastled.js` for dynamic eval in worker
2. `mainScriptUrlOrBlob` — tells Emscripten where to find `fastled.js` for pthreads
3. `locateFile` for `.wasm` — resolves `fastled.wasm` path

Without this fix, the WASM worker fails to load `fastled.js`/`fastled.wasm`,
causing silent initialization failure in the browser.

**Verify after rebuild:**
```bash
grep 'new URL(' <output_dir>/fastled_background_worker.js
# Should show: new URL("./fastled.js", ...)
# NOT:         new URL("../../fastled.js", ...)
```

---

## Rebuild Docker Image

**Status:** BLOCKED — Docker image is stale, compilation fails.

The local code (commit `b085d44`) already fixes `run_compile.py` to remove the `index.js` check, but the Docker image `niteris/fastled-wasm:latest` still has the old version. **The image must be rebuilt and pushed.**

```bash
cd ~/dev/fastled-wasm-compiler
docker build -t niteris/fastled-wasm:latest .
docker push niteris/fastled-wasm:latest
# Then remove the stale container:
docker rm -f fastled-wasm-container
# Verify:
cd ~/dev/fastled9
fastled --just-compile examples/wasm
```

**Error reproduced from `fastled --just-compile examples/wasm`:**
```
FileNotFoundError: Missing required paths: src/platforms/wasm/compiler/index.js
```

**Docker container version** (`run_compile.py` line ~98): Still checks for `index_js_src = assets_dir / "index.js"`
**Local checkout version** (`run_compile.py` line 120): Fixed — only checks `[compiler_root, assets_dir]`

---

## Summary (Full Migration)

The upstream FastLED repo has migrated its WASM frontend from raw JavaScript to TypeScript + Vite. The `copy_output_files_and_create_manifest()` function in `src/fastled_wasm_compiler/copy_files_and_output_manifest.py` copies raw source files that are now `.ts` (not browser-executable). It must be updated to use Vite-built output from `dist/`.

## Problem

`copy_output_files_and_create_manifest()` copies these from the assets directory (`src/platforms/wasm/compiler/`):

- `index.html`, `index.css` from `assets_dir`
- `modules/` recursively via `shutil.copytree`
- `vendor/` recursively if exists
- `index.js` from `assets_dir`

**After the migration:**
- `index.js` is now `index.ts` (not browser-executable)
- `modules/` contains `.ts` files (not browser-executable)
- `vendor/` is deleted entirely (Three.js is now an npm dependency)
- New build output lives in `dist/` after running `npx vite build`

## New Output Structure (from `dist/`)

```
dist/
├── index.html                           (9 KB)
├── index.js                             (1.8 MB - bundled app + Three.js)
├── index.js.map                         (source map)
├── index.css                            (47 KB)
├── fastled_background_worker.js         (26 KB - web worker)
├── fastled_background_worker.js.map     (source map)
├── audio_worklet_processor.js           (4 KB - audio worklet)
└── assets/                              (code-split chunks, hashed filenames)
    ├── three.module-XXXXXXXX.js         (1.2 MB)
    ├── graphics_manager-XXXXXXXX.js
    ├── graphics_manager_threejs-XXXXXXXX.js
    ├── ... (more hashed chunks)
    └── *.js.map                         (source maps)
```

## Required Changes

### 1. Update `copy_output_files_and_create_manifest()` in `src/fastled_wasm_compiler/copy_files_and_output_manifest.py`

Replace the individual file copy blocks (index.html, index.css, index.js, modules/, vendor/) with a copy from `dist/`:

```python
# NEW: Copy Vite build output instead of raw source files
compiler_dir = assets_modules.parent  # src/platforms/wasm/compiler
dist_dir = compiler_dir / "dist"

if dist_dir.exists():
    # Copy everything from dist/ (Vite-built, browser-ready)
    for item in dist_dir.iterdir():
        dest = out_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
else:
    raise RuntimeError(
        f"Vite build output not found at {dist_dir}. "
        f"Run 'npm install && npx vite build' in {compiler_dir}"
    )

# Keep existing data files + manifest generation unchanged
```

### 2. Add Vite build step (or require pre-built `dist/`)

**Option A — Build at compile time (recommended for Docker):**

Add a build step before the copy, either in `cli.py` or a new helper:

```python
def _ensure_vite_built(compiler_dir: Path) -> Path:
    """Ensure Vite build output exists. Build if necessary."""
    dist_dir = compiler_dir / "dist"
    if dist_dir.exists():
        return dist_dir

    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("Node.js is required for frontend build.")

    if not (compiler_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=compiler_dir, check=True)

    print("Building frontend with Vite...")
    result = subprocess.run([npx, "vite", "build"], cwd=compiler_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Vite build failed:\n{result.stderr}")

    return dist_dir
```

**Option B — Require pre-built `dist/` (simpler):**

Just check that `dist/` exists and error with a clear message if not. The upstream repo or CI pre-builds it.

### 3. Add Node.js to the Docker image

**File:** `Dockerfile`

The Docker image (based on `emscripten/emsdk`) does NOT currently have Node.js in PATH. Two options:

**Option A — Use EMSDK's bundled Node (already present):**
```dockerfile
# The emsdk image includes Node.js, just add it to PATH
ENV PATH="${EMSDK}/node/$(ls ${EMSDK}/node/)/bin:${PATH}"
```

**Option B — Install system Node.js:**
```dockerfile
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*
```

### 4. Update `sync.py` — detect `.ts` file changes

**File:** `src/fastled_wasm_compiler/sync.py`

The web asset sync logic (around line 612) detects changes to `.js`, `.mjs`, `.css`, `.html` files in the compiler directory. With the migration, source files are `.ts`:

- Add `*.ts` to the file extension list that triggers web asset sync
- When `.ts` changes are detected, the stale `dist/` needs to be rebuilt

Look for `ASSET_ONLY_EXTENSIONS` or similar and add `.ts`:
```python
ASSET_ONLY_EXTENSIONS = ["*.js", "*.mjs", "*.ts", "*.html", "*.css"]
```

### 5. Update CLI `--assets-dirs` handling

**File:** `src/fastled_wasm_compiler/cli.py`

The `--assets-dirs` argument currently defaults to `FASTLED_SRC / "platforms" / "wasm" / "compiler"` (the raw source directory). After migration, the function should either:
- Auto-detect `dist/` subdirectory within the assets dir
- Accept a separate `--assets-dist-dir` override
- Build with Vite before copying if `dist/` is missing

## How FastLED Source is Located

Path resolution (`src/fastled_wasm_compiler/paths.py`):
- Default: `~/.fastled-wasm-compiler/fastled/` (home directory)
- Docker: `ENV_FASTLED_ROOT=/git/fastled` (set in Dockerfile)
- Override: `ENV_FASTLED_ROOT` environment variable
- Assets dir: `FASTLED_SRC / "platforms" / "wasm" / "compiler"`

## Testing Against the Upstream Repo

Use `~/dev/fastled9` as the test source:

```bash
# 1. Ensure fastled9 frontend is built
cd ~/dev/fastled9/src/platforms/wasm/compiler
npm install
npx vite build

# 2. Run the compiler pointing at fastled9
cd ~/dev/fastled-wasm-compiler
ENV_FASTLED_ROOT=~/dev/fastled9 uv run fastled-wasm-compiler --example Blink

# 3. Verify output structure in the compilation output
# Expected: index.html, index.js, index.css, assets/,
#   fastled_background_worker.js, audio_worklet_processor.js
# NOT expected: modules/, vendor/

# 4. Run the Playwright e2e test from fastled9
cd ~/dev/fastled9
uv run ci/wasm_test.py wasm
# Expected: "Success: FastLED.js initialized (controller running, worker active)"
```

## Reference Implementation

See `~/dev/fastled9/ci/wasm_build.py` → `copy_templates()` (line 429) for a working implementation of the Vite build + dist copy pattern.

## Validation Checklist

- [ ] No `modules/` directory in output (bundled into `index.js`)
- [ ] No `vendor/` directory in output (Three.js in `assets/` chunks)
- [ ] `assets/` directory present with hashed `.js` chunk files
- [ ] `fastled_background_worker.js` present at root level
- [ ] `audio_worklet_processor.js` present at root level
- [ ] `index.html` loads correctly in browser
- [ ] WebWorker starts successfully (no "Worker error" in console)
- [ ] FastLED initializes and renders frames
- [ ] Docker image builds and compiles successfully
- [ ] `sync.py` detects `.ts` file changes and triggers rebuild
- [ ] Data files + `files.json` manifest still generated correctly

## Files to Modify

| File | Change |
|------|--------|
| `src/fastled_wasm_compiler/copy_files_and_output_manifest.py` | Copy from `dist/` instead of raw source |
| `src/fastled_wasm_compiler/cli.py` | Handle `dist/` auto-detection or new CLI flag |
| `src/fastled_wasm_compiler/sync.py` | Add `.ts` to detected file extensions |
| `Dockerfile` | Add Node.js for Vite build capability |

## MIME Type Gotcha

If this repo uses Python HTTP serving anywhere, ensure `.js` files are served as `application/javascript`, not `text/plain`. ES modules fail to load with wrong MIME type. Fix:

```python
class MimeHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".wasm": "application/wasm",
        ".json": "application/json",
        ".css": "text/css",
    }
```
