import os
import warnings
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile_all_libs import compile_all_libs
from fastled_wasm_compiler.paths import FASTLED_SRC, VOLUME_MAPPED_SRC
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args
from fastled_wasm_compiler.sync import sync_fastled

_RW_LOCK = fasteners.ReaderWriterLock()


class Compiler:

    def __init__(self, volume_mapped_src: Path | None = None) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.volume_mapped_src: Path = (
            volume_mapped_src if volume_mapped_src else VOLUME_MAPPED_SRC
        )
        self.rwlock = _RW_LOCK

    def compile(self, args: Args) -> int:
        err = self.update_src(self.volume_mapped_src)
        if err:
            warnings.warn(f"Error updating source: {err}")

        clear_cache = args.clear_ccache
        if clear_cache:
            with self.rwlock.write_lock():
                # Clear the ccache
                print("Clearing ccache...")
                os.system("ccache -C")
                args.clear_ccache = False
        with self.rwlock.read_lock():
            return run_compiler_with_args(args)

    def update_src(self, src_to_merge_from: Path | None = None) -> Exception | None:
        """
        Update the source directory.
        """

        src_to_merge_from = src_to_merge_from or self.volume_mapped_src
        assert isinstance(
            src_to_merge_from, Path
        ), f"src_to_merge_from must be a Path, got {type(src_to_merge_from)}"
        if not src_to_merge_from.exists():
            print("Skipping fastled src update: no source directory")
            return None  # Nothing to do

        if not (src_to_merge_from / "FastLED.h").exists():
            return FileNotFoundError(f"FastLED.h not found in {src_to_merge_from}")

        files_will_change = sync_fastled(
            src=src_to_merge_from, dst=Path("/git/fastled/src"), dryrun=True
        )

        if not files_will_change:
            print("No files changed, skipping rsync")
            return None

        # Perform the actual sync, this time behind the write lock
        with self.rwlock.write_lock():
            print("Performing rsync")
            # Perform the actual sync
            # from fastled_wasm_compiler.sync import sync_fastled
            # sync_fastled(src=src, dst=self.rsync_dest_root_src, dryrun=False)

            files_changed = sync_fastled(
                src=src_to_merge_from, dst=FASTLED_SRC, dryrun=True
            )
        if not files_changed:
            print("No files changed after rsync")
            return None

        rtn = compile_all_libs(
            src_to_merge_from.as_posix(),
            "/build",
            build_modes=["debug", "quick", "release"],
        )
        if rtn != 0:
            print(f"Error compiling all libs: {rtn}")
            return Exception(f"Error compiling all libs: {rtn}")
        return None
