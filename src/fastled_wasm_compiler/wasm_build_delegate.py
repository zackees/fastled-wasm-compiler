"""Delegate compilation to FastLED's ci/wasm_build.py when available.

When the FastLED repo includes ci/wasm_build.py, we delegate the entire
compilation to it. This build system uses Meson+Ninja with command
capture/caching via clang-tool-chain, providing fast incremental rebuilds.

Falls back to the existing standalone pipeline for older FastLED versions
or downloaded archives that lack ci/wasm_build.py.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from fastled_wasm_compiler.paths import FASTLED_ROOT
from fastled_wasm_compiler.print_banner import banner


def _get_clang_tool_chain_emscripten_dir() -> Path | None:
    """Get the clang-tool-chain Emscripten installation directory."""
    env_path = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    base_dir = Path(env_path) if env_path else Path.home() / ".clang-tool-chain"
    emscripten_base = base_dir / "emscripten"

    if not emscripten_base.exists():
        return None

    if (emscripten_base / "emscripten" / "emcc.py").exists():
        return emscripten_base

    for subdir in emscripten_base.iterdir():
        if subdir.is_dir():
            for arch_dir in subdir.iterdir():
                if arch_dir.is_dir():
                    if (arch_dir / "emscripten" / "emcc.py").exists():
                        return arch_dir
            if (subdir / "emscripten" / "emcc.py").exists():
                return subdir

    return None


def _setup_emscripten_env(env: dict[str, str]) -> None:
    """Set up Emscripten environment variables for ci/wasm_build.py."""
    clang_tool_chain_dir = _get_clang_tool_chain_emscripten_dir()
    if not clang_tool_chain_dir:
        return

    emscripten_dir = clang_tool_chain_dir / "emscripten"
    config_path = clang_tool_chain_dir / ".emscripten"
    bin_dir = clang_tool_chain_dir / "bin"

    if emscripten_dir.exists():
        env["EMSCRIPTEN"] = str(emscripten_dir)
        env["EMSCRIPTEN_ROOT"] = str(emscripten_dir)
    if config_path.exists():
        env["EM_CONFIG"] = str(config_path)
    env["EMSDK_PYTHON"] = sys.executable
    env["EMCC_SKIP_SANITY_CHECK"] = "1"
    if bin_dir.exists():
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"


def has_wasm_build_system(fastled_root: Path | None = None) -> bool:
    """Check if the FastLED repo has ci/wasm_build.py."""
    root = fastled_root or FASTLED_ROOT
    return (root / "ci" / "wasm_build.py").exists()


_BUILD_MODE_MAP = {
    "debug": "debug",
    "quick": "quick",
    "release": "release",
    "fast_debug": "quick",  # No direct equivalent, map to quick
}


def compile_via_wasm_build(
    sketch_dir: Path,
    build_dir: Path,
    build_mode: str,
    fastled_root: Path | None = None,
) -> int:
    """Delegate compilation to FastLED's ci/wasm_build.py.

    ci/wasm_build.py uses Meson+Ninja with command capture/caching via
    clang-tool-chain for fast incremental rebuilds. It handles .ino file
    processing, library compilation, and linking internally.

    Args:
        sketch_dir: Directory containing the sketch source files.
        build_dir: Directory for build output (fastled.js, fastled.wasm).
        build_mode: Build mode string (debug, quick, release, fast_debug).
        fastled_root: Path to the FastLED repo root. Defaults to FASTLED_ROOT.

    Returns:
        0 on success, non-zero on failure.
    """
    root = fastled_root or FASTLED_ROOT
    mode = _BUILD_MODE_MAP.get(build_mode.lower(), "quick")

    # Derive the example name from the .ino file inside the sketch directory,
    # not the directory name (which is typically just "src").
    # wasm_build.py expects --example <name> where examples/<name>/<name>.ino exists.
    ino_files = list(sketch_dir.glob("*.ino"))
    if ino_files:
        sketch_name = ino_files[0].stem
    else:
        sketch_name = sketch_dir.name
    example_dir = root / "examples" / sketch_name

    # Check if sketch is already in the FastLED examples tree
    try:
        sketch_dir.relative_to(root / "examples")
        is_in_tree = True
    except ValueError:
        is_in_tree = False

    build_dir.mkdir(parents=True, exist_ok=True)
    output_js = build_dir / "fastled.js"

    # ci/wasm_build.py uses relative imports (from ci.wasm_flags import ...),
    # so it must be invoked from the FastLED repo root.
    uv = shutil.which("uv")
    wasm_build_script = str(root / "ci" / "wasm_build.py")

    if uv:
        cmd = [
            uv,
            "run",
            "python",
            wasm_build_script,
            "--example",
            sketch_name,
            "-o",
            str(output_js),
            "--mode",
            mode,
        ]
    else:
        cmd = [
            sys.executable,
            wasm_build_script,
            "--example",
            sketch_name,
            "-o",
            str(output_js),
            "--mode",
            mode,
        ]

    env = os.environ.copy()
    _setup_emscripten_env(env)

    # Symlink sketch into examples/ if not already there
    needs_cleanup = False
    if not is_in_tree:
        if not example_dir.exists():
            example_dir.symlink_to(sketch_dir, target_is_directory=True)
            needs_cleanup = True

    try:
        print(banner(f"Delegating to FastLED build system (mode: {mode})"))
        print(f"  Command: {subprocess.list2cmdline(cmd)}")
        print(f"  Working directory: {root}")
        result = subprocess.run(cmd, cwd=str(root), env=env)
        return result.returncode
    finally:
        if needs_cleanup and example_dir.is_symlink():
            example_dir.unlink()
