import os
from pathlib import Path


def path_or_default(default: str, env_var: str) -> Path:
    """Return the path from the environment variable or the default."""
    return Path(os.environ.get(env_var, default))


# Cross-platform paths using environment variables
FASTLED_ROOT = path_or_default(
    str(Path.home() / ".fastled-wasm-compiler" / "fastled"), "ENV_FASTLED_ROOT"
)

FASTLED_SRC = FASTLED_ROOT / "src"

# EMSDK paths - use environment variable for flexibility
EMSDK_ROOT = path_or_default(
    str(Path.home() / ".fastled-wasm-compiler" / "emsdk"), "ENV_EMSDK_ROOT"
)

# Volume mapped paths for container compatibility
VOLUME_MAPPED_SRC = path_or_default(str(FASTLED_SRC), "ENV_VOLUME_MAPPED_SRC")

# Sketch and build paths - use relative paths when possible
SKETCH_ROOT = path_or_default("src", "ENV_SKETCH_ROOT")
BUILD_ROOT = path_or_default("build", "ENV_BUILD_ROOT")

# Container paths - these are the paths inside the Docker container
CONTAINER_JS_ROOT = "/js"


# Source path mappings for cross-platform compatibility
def get_fastled_source_path() -> str:
    """Get the FastLED source path for path resolution."""
    # Use environment variable or default to relative path
    return os.environ.get("ENV_FASTLED_SOURCE_PATH", "git/fastled/src")


def get_emsdk_path() -> str:
    """Get the EMSDK path for path resolution."""
    # Use environment variable or default to relative path
    return os.environ.get("ENV_EMSDK_PATH", "emsdk")


def get_sketch_path() -> str:
    """Get the sketch path for path resolution."""
    # Use environment variable or convert SKETCH_ROOT to relative
    env_path = os.environ.get("ENV_SKETCH_PATH")
    if env_path:
        return env_path

    # Convert absolute path to relative if needed
    sketch_path = str(SKETCH_ROOT)
    if os.path.isabs(sketch_path):
        # For absolute paths, try to make them relative to current working directory
        try:
            return os.path.relpath(sketch_path)
        except ValueError:
            # If that fails (e.g., different drive on Windows), use as-is
            return sketch_path
    return sketch_path
