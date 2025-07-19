import os
import platform
from pathlib import Path

_IS_WINDOWS = platform.system() == "Windows"
_DEFAULT_BUILD_ROOT = "/build" if not _IS_WINDOWS else "build"

# Project root directory (repository root)
PROJECT_ROOT = Path(__file__).parent.parent.parent


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
SKETCH_ROOT = path_or_default("/js/src", "ENV_SKETCH_ROOT")
BUILD_ROOT = path_or_default(_DEFAULT_BUILD_ROOT, "ENV_BUILD_ROOT")

# Container paths - these are the paths inside the Docker container
CONTAINER_JS_ROOT = "/js"


def is_volume_mapped_source_defined() -> bool:
    """Check if volume mapped source is explicitly defined.

    Returns:
        True if ENV_VOLUME_MAPPED_SRC is set, False otherwise
    """
    return os.environ.get("ENV_VOLUME_MAPPED_SRC") is not None


def can_use_thin_lto() -> bool:
    """Determine if thin LTO can be used based on volume mapped source availability.

    When volume mapped source is not defined, cannot use thin LTO (forced to use regular archives).
    When volume mapped source is defined, can use thin LTO (respects the NO_THIN_LTO flag).

    Returns:
        True if thin LTO can be used, False to force regular archives
    """
    # If volume mapped source is not defined, always use regular archives (no thin LTO)
    if not is_volume_mapped_source_defined():
        return False

    # Volume mapped source is defined, respect NO_THIN_LTO flag
    no_thin_lto = os.environ.get("NO_THIN_LTO", "0") == "1"
    return not no_thin_lto


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
    # Use the same environment variable as SKETCH_ROOT for consistency
    # Always use forward slashes for cross-platform compatibility
    return str(SKETCH_ROOT).replace("\\", "/")
