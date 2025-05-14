import warnings
from pathlib import Path

# Matches what the compiler has.
FASTLED_SOURCE_PATH = "/git/fastled/src"
FASTLED_HEADERS_PATH = "/headers"
SKETCH_PATH = "/js/src"  # todo - this will change.

# As defined in the fastled-wasm-compiler.
FASTLED_PREFIX = "fastledsource"
SKETCH_PREFIX = "sketchsource"


def dwarf_path_to_file_path(
    request_path: str,
) -> Path | Exception:
    """Resolve the path for drawfsource."""
    path_or_error = _dwarf_path_to_file_path_inner(request_path)
    if isinstance(path_or_error, Exception):
        return path_or_error
    path: str = path_or_error
    if "//" in path:
        # this is a security check.
        path = path.replace("//", "/")
    return Path(path)


def _dwarf_path_to_file_path_inner(
    request_path: str,
) -> str | Exception:
    """Resolve the path for drawfsource."""
    if (
        ".." in request_path
    ):  # we never have .. in the path so someone is trying weird stuff.
        warnings.warn(f"Invalid path: {request_path}")
        return Exception(f"Invalid path: {request_path}")
    if request_path.startswith("/"):
        request_path = request_path[1:]  # Remove leading slash
    # even easier, just find the last index of "sketchsource" and "fastledsource".
    # Which ever one is greater, use that.
    fastled_index = request_path.rfind(FASTLED_PREFIX)
    sketch_index = request_path.rfind(SKETCH_PREFIX)
    if fastled_index == -1 and sketch_index == -1:
        warnings.warn(f"Invalid path: {request_path}")
        return Exception(f"Invalid path: {request_path}")
    if fastled_index > sketch_index:
        # fastled source
        path: str = request_path[fastled_index + len(FASTLED_PREFIX) :]
        # a security check.
        if not path.startswith("/") and FASTLED_SOURCE_PATH.startswith("/"):
            path = "/" + path
        return path
    if sketch_index != -1:
        # sketch source (or one of the headers that got compiled in)
        path: str = request_path[sketch_index + len(SKETCH_PREFIX) :]
        # a security check.
        if not path.startswith("/") and SKETCH_PATH.startswith("/"):
            path = "/" + path
        if path.startswith(FASTLED_HEADERS_PATH):
            # this is a header file that got compiled in the sketch directory.
            relative = path[len(FASTLED_HEADERS_PATH) :]
            if relative.startswith("/"):
                relative = relative[1:]
            return f"{FASTLED_HEADERS_PATH}/{relative}"
        if path.startswith(SKETCH_PATH):
            # this is a sketch file.
            path = path[len(SKETCH_PATH) :]
            return f"{SKETCH_PATH}/{path}"
    # this should never happen.
    warnings.warn(f"Invalid path: {request_path}")
    return Exception(f"Invalid path: {request_path}")
