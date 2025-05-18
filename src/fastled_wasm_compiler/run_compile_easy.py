from pathlib import Path

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args


def run_compiler(
    compiler_root: Path,
    assets_dirs: Path,
    mapped_dir: Path,  # Sketch directory, note that this is weird. Explained elsewhere in code.
    keep_files: bool,
    profile: bool,
    disable_auto_clean: bool,
    no_platformio: bool,
    debug: bool,
    quick: bool,
    release: bool,
    clear_ccache: bool = False,
) -> int:
    """
    Run the FastLED WASM compiler with the provided arguments.

    Args:
        compiler_root (Path): The root directory of the compiler where the magic happens.
        assets_dirs (Path): The directory containing asset files.
        mapped_dir (Path): The directory to map source files.
        keep_files (bool): Flag to keep source files after compilation.
        only_copy (bool): Flag to only copy files without compiling.
        only_insert_header (bool): Flag to only insert header files.
        only_compile (bool): Flag to only compile without copying.
        profile (bool): Flag to enable profiling of the build system.
        disable_auto_clean (bool): Flag to disable automatic cleaning.
        no_platformio (bool): Flag to disable PlatformIO.
        debug (bool): Flag to enable debug mode.
        quick (bool): Flag to enable quick mode.
        release (bool): Flag to enable release mode.

    Returns:
        int: Exit code of the compilation process.
    """

    args = Args(
        compiler_root=compiler_root,
        assets_dirs=assets_dirs,
        mapped_dir=mapped_dir,
        keep_files=keep_files,
        only_copy=False,
        only_insert_header=False,
        only_compile=False,
        profile=profile,
        disable_auto_clean=disable_auto_clean,
        no_platformio=no_platformio,
        debug=debug,
        quick=quick,
        release=release,
        clear_ccache=clear_ccache,
    )
    rtn: int = run_compiler_with_args(args)
    return rtn
