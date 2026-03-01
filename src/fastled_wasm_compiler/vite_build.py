"""Helper to ensure Vite-built frontend output exists."""

import shutil
import subprocess
from pathlib import Path


def ensure_vite_built(compiler_dir: Path) -> Path:
    """Ensure Vite build output exists in compiler_dir/dist/.

    If dist/ already exists, returns immediately. Otherwise, runs
    npm install (if needed) and npx vite build.

    Args:
        compiler_dir: Path to src/platforms/wasm/compiler/

    Returns:
        Path to the dist/ directory.

    Raises:
        RuntimeError: If Node.js is not available or the build fails.
    """
    dist_dir = compiler_dir / "dist"
    if dist_dir.exists():
        # Verify dist/ has essential files, not just orphaned .map files
        essential_files = ["index.html", "index.js"]
        if all((dist_dir / f).exists() for f in essential_files):
            return dist_dir
        print("Vite dist/ directory is incomplete, rebuilding...")

    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError(
            "npx not found on PATH. Node.js is required to build the "
            + "TypeScript frontend with Vite."
        )

    if not (compiler_dir / "node_modules").exists():
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError(
                "npm not found on PATH. Node.js is required to build the "
                + "TypeScript frontend with Vite."
            )
        print("Installing frontend dependencies...")
        result = subprocess.run(
            [npm, "install"],
            cwd=compiler_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"npm install failed (exit code {result.returncode}):\n{result.stderr}"
            )

    print("Building frontend with Vite...")
    result = subprocess.run(
        [npx, "vite", "build"],
        cwd=compiler_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Vite build failed (exit code {result.returncode}):\n{result.stderr}"
        )

    if not dist_dir.exists():
        raise RuntimeError("Vite build succeeded but dist/ directory was not created.")

    return dist_dir
