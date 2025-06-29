import logging
import warnings
from pathlib import Path

from fastled_wasm_compiler.paths import (
    FASTLED_SRC,
    SKETCH_ROOT,
)

logger = logging.getLogger(__name__)

# Matches what the compiler has: sorted from most complex to least complex.
FASTLED_SOURCE_PATH = FASTLED_SRC.as_posix()
SKETCH_PATH = SKETCH_ROOT.as_posix()
FASTLED_HEADERS_PATH = FASTLED_SRC.as_posix()
EMSDK_PATH = "/emsdk"


# As defined in the fastled-wasm-compiler.
FASTLED_PREFIX = "fastledsource"
SKETCH_PREFIX = "sketchsource"
DWARF_PREFIX = "dwarfsource"

SOURCE_PATHS = [
    FASTLED_SOURCE_PATH,
    FASTLED_HEADERS_PATH,
    SKETCH_PATH,
    EMSDK_PATH,
]

# Sorted by longest first.
SOURCE_PATHS_NO_LEADING_SLASH = [p.lstrip("/") for p in SOURCE_PATHS]

PREFIXES = [FASTLED_PREFIX, SKETCH_PREFIX, DWARF_PREFIX]


def dwarf_path_to_file_path(
    request_path: str,
    check_exists=True,
) -> Path | Exception:
    """Resolve the path for dwarfsource."""
    logger.debug(f"Resolving dwarf path: {request_path}")
    path_or_error = _dwarf_path_to_file_path_inner(request_path)
    if isinstance(path_or_error, Exception):
        logger.error(f"Failed to resolve path: {request_path}, error: {path_or_error}")
        return path_or_error
    path: str = path_or_error
    if "//" in path:
        # this is a security check.
        logger.warning(f"Security check: replaced // in path: {path}")
        path = path.replace("//", "/")
    out = Path(path)
    if check_exists and not out.exists():
        logger.error(f"Path does not exist: {out}")
        return FileNotFoundError(f"Could not find path {out}")
    logger.debug(f"Resolved dwarf path {request_path} to {out}")
    return out


def prune_paths(path: str) -> str | None:
    logger.debug(f"Pruning path: {path}")
    if path.startswith("/"):
        path = path[1:]
    p: Path = Path(path)
    # pop off the leaf and store it in a buffer.
    # When you hit one of the PREFIXES, then stop
    # and return the path that was popped.
    parts = p.parts
    buffer = []
    parts_reversed = parts[::-1]
    for part in parts_reversed:
        if part in PREFIXES:
            logger.debug(f"Found prefix: {part}")
            break
        buffer.append(part)
    if not buffer:
        logger.warning(f"No valid path components found in: {path}")
        return None
    result = "/".join(buffer[::-1])
    logger.debug(f"Pruned path {path} to {result}")
    return result


def _dwarf_path_to_file_path_inner(
    request_path: str,
) -> str | Exception:
    """Resolve the path for dwarfsource."""
    logger.debug(f"Inner path resolution for: {request_path}")
    if (
        ".." in request_path
    ):  # we never have .. in the path so someone is trying weird stuff.
        msg = f"Invalid path with '..' detected: {request_path}"
        logger.warning(msg)
        warnings.warn(msg)
        return Exception(f"Invalid path: {request_path}")

    request_path_pruned = prune_paths(request_path)
    if request_path_pruned is None:
        logger.error(f"Failed to prune path: {request_path}")
        return Exception(f"Invalid path: {request_path}")

    if request_path_pruned.startswith("headers"):
        # Special case this one.
        result = request_path_pruned.replace("headers", FASTLED_SOURCE_PATH)
        logger.debug(f"Headers special case: {request_path_pruned} -> {result}")
        return result

    for i, source_path in enumerate(SOURCE_PATHS_NO_LEADING_SLASH):
        if request_path_pruned.startswith(source_path):
            suffix_path = request_path_pruned[len(source_path) :]
            if suffix_path.startswith("/"):
                suffix_path = suffix_path[1:]
            result = f"{SOURCE_PATHS[i]}/{suffix_path}"
            logger.debug(
                f"Matched source path {source_path}: {request_path_pruned} -> {result}"
            )
            return result

    logger.error(f"No matching source path found for: {request_path_pruned}")
    return Exception(f"Invalid path: {request_path}")
