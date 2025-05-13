import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Args:
    compiler_root: Path
    assets_dirs: Path
    mapped_dir: Path
    keep_files: bool
    only_copy: bool
    only_insert_header: bool
    only_compile: bool
    profile: bool
    disable_auto_clean: bool
    no_platformio: bool
    debug: bool
    quick: bool
    release: bool

    @staticmethod
    def parse_args() -> "Args":
        return _parse_args()

    def __post_init__(self):
        assert isinstance(self.compiler_root, Path)
        assert isinstance(self.assets_dirs, Path)
        assert isinstance(self.mapped_dir, Path)
        assert isinstance(self.keep_files, bool)
        assert isinstance(self.only_copy, bool)
        assert isinstance(self.only_insert_header, bool)
        assert isinstance(self.only_compile, bool)
        assert isinstance(self.profile, bool)
        assert isinstance(self.disable_auto_clean, bool)
        assert isinstance(self.no_platformio, bool)
        assert isinstance(self.debug, bool)
        assert isinstance(self.quick, bool)
        assert isinstance(self.release, bool)


def _parse_args() -> Args:
    parser = argparse.ArgumentParser(description="Compile FastLED for WASM")

    parser.add_argument("--compiler-root", type=Path, required=True)
    parser.add_argument(
        "--index-html",
        type=Path,
        required=True,
    )
    parser.add_argument("--assets-dirs", type=Path, required=True)
    parser.add_argument(
        "--mapped-dir",
        type=Path,
        default="/mapped",
        help="Directory containing source files (default: /mapped)",
    )
    parser.add_argument(
        "--keep-files", action="store_true", help="Keep source files after compilation"
    )
    parser.add_argument(
        "--only-copy",
        action="store_true",
        help="Only copy files from mapped directory to container",
    )
    parser.add_argument(
        "--only-insert-header",
        action="store_true",
        help="Only insert headers in source files",
    )
    parser.add_argument(
        "--only-compile", action="store_true", help="Only compile the project"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable profiling for compilation to see what's taking so long.",
    )

    parser.add_argument(
        "--disable-auto-clean",
        action="store_true",
        help="Massaive speed improvement to not have to rebuild everything, but flakes out sometimes.",
        default=os.getenv("DISABLE_AUTO_CLEAN", "0") == "1",
    )
    parser.add_argument(
        "--no-platformio",
        action="store_true",
        help="Don't use platformio to compile the project, use the new system of direct emcc calls.",
    )
    # Add mutually exclusive build mode group
    build_mode = parser.add_mutually_exclusive_group()
    build_mode.add_argument("--debug", action="store_true", help="Build in debug mode")
    build_mode.add_argument(
        "--quick",
        action="store_true",
        default=True,
        help="Build in quick mode (default)",
    )
    build_mode.add_argument(
        "--release", action="store_true", help="Build in release mode"
    )

    tmp = parser.parse_args()
    return Args(
        compiler_root=tmp.compiler_root,
        assets_dirs=tmp.assets_dirs,
        mapped_dir=tmp.mapped_dir,
        keep_files=tmp.keep_files,
        only_copy=tmp.only_copy,
        only_insert_header=tmp.only_insert_header,
        only_compile=tmp.only_compile,
        profile=tmp.profile,
        disable_auto_clean=tmp.disable_auto_clean,
        no_platformio=tmp.no_platformio,
        debug=tmp.debug,
        quick=tmp.quick,
        release=tmp.release,
    )
