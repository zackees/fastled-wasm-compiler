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
    clear_ccache: bool

    @staticmethod
    def parse_args(args: list[str] | None = None) -> "Args":
        return _parse_args(args)

    def to_cmd_args(self) -> list[str]:
        args = [
            "--compiler-root",
            str(self.compiler_root),
            "--assets-dirs",
            str(self.assets_dirs),
            "--mapped-dir",
            str(self.mapped_dir),
            "--keep-files" if self.keep_files else "",
            "--only-copy" if self.only_copy else "",
            "--only-insert-header" if self.only_insert_header else "",
            "--only-compile" if self.only_compile else "",
            "--profile" if self.profile else "",
            "--disable-auto-clean" if self.disable_auto_clean else "",
            "--no-platformio" if self.no_platformio else "",
            "--debug" if self.debug else "",
            "--quick" if self.quick else "",
            "--release" if self.release else "",
            "--clear-ccache" if self.clear_ccache else "",
        ]
        return [arg for arg in args if arg]

    # equal
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Args):
            return NotImplemented
        return (
            self.compiler_root == other.compiler_root
            and self.assets_dirs == other.assets_dirs
            and self.mapped_dir == other.mapped_dir
            and self.keep_files == other.keep_files
            and self.only_copy == other.only_copy
            and self.only_insert_header == other.only_insert_header
            and self.only_compile == other.only_compile
            and self.profile == other.profile
            and self.disable_auto_clean == other.disable_auto_clean
            and self.no_platformio == other.no_platformio
            and self.debug == other.debug
            and self.quick == other.quick
            and self.release == other.release
            and self.clear_ccache == other.clear_ccache
        )

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

    def __str__(self):
        return (
            f"Args(compiler_root={self.compiler_root}, "
            f"assets_dirs={self.assets_dirs}, "
            f"mapped_dir={self.mapped_dir}, "
            f"keep_files={self.keep_files}, "
            f"only_copy={self.only_copy}, "
            f"only_insert_header={self.only_insert_header}, "
            f"only_compile={self.only_compile}, "
            f"profile={self.profile}, "
            f"disable_auto_clean={self.disable_auto_clean}, "
            f"no_platformio={self.no_platformio}, "
            f"debug={self.debug}, "
            f"quick={self.quick}, "
            f"release={self.release})"
        )


def _parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(description="Compile FastLED for WASM")

    parser.add_argument("--compiler-root", type=Path, required=True)
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
    parser.add_argument(
        "--clear-ccache",
        action="store_true",
        help="Clear the ccache before compilation.",
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

    tmp = parser.parse_args(args)
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
        clear_ccache=tmp.clear_ccache,
    )
