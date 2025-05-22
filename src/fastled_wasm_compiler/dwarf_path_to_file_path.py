import warnings
from pathlib import Path

# Matches what the compiler has: sorted from most complex to least complex.
FASTLED_SOURCE_PATH = "/git/fastled/src"
SKETCH_PATH = "/js/src"  # todo - this will change.
STDLIB_PATH = "/emsdk/emscripten/cache/sysroot/include"


# As defined in the fastled-wasm-compiler.
FASTLED_PREFIX = "FastLED"
SKETCH_PREFIX = "Sketch"
STDLIB_PREFIX = "stdlib"

PATH_MAP: dict[str, str] = {
    "FastLED": FASTLED_SOURCE_PATH,
    "Sketch": SKETCH_PATH,
    "stdlib": STDLIB_PATH,
}


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
        # this is a security check.
        request_path = request_path[1:]
    first, rest = request_path.split("/", 1)
    prefix: str | None = PATH_MAP.get(first)
    if prefix is None:
        return Exception(f"Invalid prefix: {first}")
    return prefix + "/" + rest
