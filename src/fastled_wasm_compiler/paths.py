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
    """Check if volume mapped source is explicitly defined and exists.

    Volume mapping is considered enabled when ENV_VOLUME_MAPPED_SRC is set
    AND the path actually exists. This matches the behavior in other parts
    of the codebase that check volume_mapped_src.exists().

    Returns:
        True if ENV_VOLUME_MAPPED_SRC is set and the path exists, False otherwise
    """
    env_value = os.environ.get("ENV_VOLUME_MAPPED_SRC")
    if env_value is None:
        return False

    # Check if the path actually exists
    volume_mapped_path = Path(env_value)
    return volume_mapped_path.exists()


def get_archive_build_mode() -> str:
    """Determine which archive type to build exclusively.

    Returns:
        "thin" | "regular" | "both"
    """
    mode = os.environ.get("ARCHIVE_BUILD_MODE", "regular").lower()
    if mode in ["thin", "regular", "both"]:
        return mode
    else:
        # Invalid value, default to "regular" (best performance)
        return "regular"


def validate_archive_configuration() -> None:
    """Validate that archive configuration is consistent.

    Raises:
        RuntimeError: If configuration is inconsistent
    """
    archive_mode = get_archive_build_mode()

    if archive_mode == "thin":
        # Ensure NO_THIN_LTO=0 (or not set)
        if os.environ.get("NO_THIN_LTO") == "1":
            raise RuntimeError(
                "Conflicting configuration: ARCHIVE_BUILD_MODE=thin but NO_THIN_LTO=1. "
                + "For thin archives only, set NO_THIN_LTO=0 or leave unset."
            )
    elif archive_mode == "regular":
        # Ensure NO_THIN_LTO=1
        if os.environ.get("NO_THIN_LTO") == "0":
            raise RuntimeError(
                "Conflicting configuration: ARCHIVE_BUILD_MODE=regular but NO_THIN_LTO=0. "
                + "For regular archives only, set NO_THIN_LTO=1."
            )


def get_expected_archive_path(build_mode: str) -> Path:
    """Get the path to the expected archive based on configuration.

    Args:
        build_mode: Build mode (DEBUG, QUICK, RELEASE)

    Returns:
        Path to the expected archive file
    """
    build_mode_lower = build_mode.lower()
    archive_mode = get_archive_build_mode()

    if archive_mode == "thin":
        return BUILD_ROOT / build_mode_lower / "libfastled-thin.a"
    elif archive_mode == "regular":
        return BUILD_ROOT / build_mode_lower / "libfastled.a"
    else:
        # "both" mode - select based on can_use_thin_lto()
        if can_use_thin_lto():
            return BUILD_ROOT / build_mode_lower / "libfastled-thin.a"
        else:
            return BUILD_ROOT / build_mode_lower / "libfastled.a"


def can_use_thin_lto() -> bool:
    """Determine if thin LTO can be used based on volume mapped source availability and configuration.

    When volume mapped source is not defined, cannot use thin LTO (forced to use regular archives).
    When volume mapped source is defined, can use thin LTO (respects the NO_THIN_LTO flag).

    This function now also respects exclusive archive mode settings.

    Returns:
        True if thin LTO can be used, False to force regular archives
    """
    # Check for exclusive archive mode first
    archive_mode = get_archive_build_mode()
    if archive_mode == "thin":
        return True
    elif archive_mode == "regular":
        return False

    # Original logic for "both" mode
    # If volume mapped source is not defined, always use regular archives (no thin LTO)
    if not is_volume_mapped_source_defined():
        return False

    # Volume mapped source is defined, respect NO_THIN_LTO flag
    no_thin_lto = os.environ.get("NO_THIN_LTO", "0") == "1"
    return not no_thin_lto


def get_fastled_library_path(build_mode: str) -> Path:
    """Get the correct FastLED library path based on configuration.

    Args:
        build_mode: Build mode (DEBUG, QUICK, RELEASE)

    Returns:
        Path to the expected archive file

    Raises:
        RuntimeError: If the expected library file doesn't exist
    """
    # Validate configuration first
    validate_archive_configuration()

    expected_path = get_expected_archive_path(build_mode)

    if not expected_path.exists():
        archive_mode = get_archive_build_mode()
        build_mode_lower = build_mode.lower()
        archive_type = "thin" if "thin" in expected_path.name else "regular"

        error_msg = (
            f"❌ Required FastLED library not found: {expected_path}\n"
            + f"   Build mode: {build_mode} ({archive_type} archive)\n"
            + f"   Archive mode: {archive_mode}\n"
            + "   Please build FastLED library first:\n"
            + f"   • uv run fastled-wasm-compiler-build-lib-lazy --{build_mode_lower}"
        )

        if archive_mode != "both":
            error_msg += f"\n   • Or use environment variable for {archive_mode} mode"

        raise RuntimeError(error_msg)

    return expected_path


# Source path mappings for cross-platform compatibility
def get_fastled_source_path() -> str:
    """Get the FastLED source path for path resolution."""
    # Use environment variable or default to absolute path
    path = os.environ.get("ENV_FASTLED_SOURCE_PATH", "/git/fastled/src")

    # On Windows with Git Bash, normalize paths that got converted
    if _IS_WINDOWS:
        git_bash_prefixes = [
            "C:/Program Files/Git/",
            "C:/Program Files (x86)/Git/",
            "/c/Program Files/Git/",
            "/c/Program Files (x86)/Git/",
            "/C:/Program Files/Git/",
            "/C:/Program Files (x86)/Git/",
        ]

        for prefix in git_bash_prefixes:
            if path.startswith(prefix):
                # Convert back to the intended relative path
                relative_path = path[len(prefix) :]
                # Ensure the relative path starts with / for absolute-style resolution
                if not relative_path.startswith("/"):
                    relative_path = "/" + relative_path
                return relative_path

    return path


def get_emsdk_path() -> str:
    """Get the EMSDK path for path resolution."""
    # Use environment variable or default to absolute path
    return os.environ.get("ENV_EMSDK_PATH", "/emsdk")


def get_sketch_path() -> str:
    """Get the sketch path for path resolution."""
    # Use the same environment variable as SKETCH_ROOT for consistency
    # Always use forward slashes for cross-platform compatibility
    return str(SKETCH_ROOT).replace("\\", "/")
