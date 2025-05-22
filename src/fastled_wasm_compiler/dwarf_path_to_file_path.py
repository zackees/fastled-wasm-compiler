import warnings
from pathlib import Path

from fastled_wasm_compiler.paths import (
    FASTLED_SRC,
)

# Matches what the compiler has: sorted from most complex to least complex.
FASTLED_SOURCE_PATH = FASTLED_SRC.as_posix()
SKETCH_PATH = "/js/src"  # todo - this will change.
FASTLED_HEADERS_PATH = FASTLED_SRC.as_posix()
EMSDK_PATH = "/emsdk"


# As defined in the fastled-wasm-compiler.
FASTLED_PREFIX = "fastledsource"
SKETCH_PREFIX = "sketchsource"

SOURCE_PATHS = [
    FASTLED_SOURCE_PATH,
    FASTLED_HEADERS_PATH,
    SKETCH_PATH,
    EMSDK_PATH,
]

# Sorted by longest first.
SOURCE_PATHS_NO_LEADING_SLASH = [p.lstrip("/") for p in SOURCE_PATHS]

PREFIXES = [
    FASTLED_PREFIX,
    SKETCH_PREFIX,
]


def dwarf_path_to_file_path(
    request_path: str,
    check_exists=True,
) -> Path | Exception:
    """Resolve the path for drawfsource."""
    path_or_error = _dwarf_path_to_file_path_inner(request_path)
    if isinstance(path_or_error, Exception):
        return path_or_error
    path: str = path_or_error
    if "//" in path:
        # this is a security check.
        path = path.replace("//", "/")
    out = Path(path)
    if check_exists and not out.exists():
        return FileNotFoundError(f"Could not find path {out}")
    return out


def prune_paths(path: str) -> str | None:
    p: Path = Path(path)
    # pop off the leaf and store it in a buffer.
    # When you hit one of the PREFIXES, then stop
    # and return the path that was popped.
    parts = p.parts
    buffer = []
    parts_reversed = parts[::-1]
    for part in parts_reversed:
        if part in PREFIXES:
            break
        buffer.append(part)
    if not buffer:
        return None
    return "/".join(buffer[::-1])


def _dwarf_path_to_file_path_inner(
    request_path: str,
) -> str | Exception:
    """Resolve the path for drawfsource."""
    if (
        ".." in request_path
    ):  # we never have .. in the path so someone is trying weird stuff.
        warnings.warn(f"Invalid path: {request_path}")
        return Exception(f"Invalid path: {request_path}")
    request_path_pruned = prune_paths(request_path)
    if request_path_pruned is None:
        return Exception(f"Invalid path: {request_path}")
    if request_path_pruned.startswith("headers"):
        # Special case this one.
        return request_path_pruned.replace("headers", FASTLED_SOURCE_PATH)
    for i, source_path in enumerate(SOURCE_PATHS_NO_LEADING_SLASH):
        if request_path_pruned.startswith(source_path):
            suffix_path = request_path_pruned[len(source_path) :]
            if suffix_path.startswith("/"):
                suffix_path = "/" + suffix_path
            return f"{SOURCE_PATHS[i]}{suffix_path}"
    return Exception(f"Invalid path: {request_path}")
