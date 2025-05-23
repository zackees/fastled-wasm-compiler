import os
import time
import warnings
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile_all_libs import compile_all_libs
from fastled_wasm_compiler.paths import FASTLED_SRC, VOLUME_MAPPED_SRC
from fastled_wasm_compiler.print_banner import print_banner
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

    def compile(self, args: Args) -> Exception | None:
        clear_cache = args.clear_ccache
        volume_is_mapped_in = self.volume_mapped_src.exists()
        system_might_be_modified = clear_cache or volume_is_mapped_in
        if system_might_be_modified:
            with self.rwlock.write_lock():
                if volume_is_mapped_in:
                    print(
                        f"Updating source directory from {self.volume_mapped_src} if necessary"
                    )
                    start = time.time()
                    err = self.update_src(src_to_merge_from=self.volume_mapped_src)
                    if isinstance(err, Exception):
                        warnings.warn(f"Error updating source: {err}")
                        return err
                    if isinstance(err, list) and len(err) > 0:
                        clear_cache = (
                            True  # Always clear cache when the source changes.
                        )
                        diff = time.time() - start
                        print_banner(
                            f"Recompile of static lib(s) source took {diff:.2f} seconds"
                        )

                if clear_cache:
                    # Clear the ccache
                    print("Clearing ccache...")
                    os.system("ccache -C")
                    args.clear_ccache = False

        with self.rwlock.read_lock():
            rtn: int = run_compiler_with_args(args)
            if rtn != 0:
                msg = f"Error: Compiler failed with code {rtn}"
                print_banner(msg)
                return Exception(msg)

    def update_src(
        self, builds: list[str] | None = None, src_to_merge_from: Path | None = None
    ) -> list[Path] | Exception:
        """
        Update the source directory.
        """

        src_to_merge_from = src_to_merge_from or self.volume_mapped_src
        assert isinstance(
            src_to_merge_from, Path
        ), f"src_to_merge_from must be a Path, got {type(src_to_merge_from)}"
        if not src_to_merge_from.exists():
            print("Skipping fastled src update: no source directory")
            return []  # Nothing to do

        if not (src_to_merge_from / "FastLED.h").exists():
            return FileNotFoundError(f"FastLED.h not found in {src_to_merge_from}")

        files_will_change: list[Path] = sync_fastled(
            src=src_to_merge_from, dst=FASTLED_SRC, dryrun=True
        )

        if not files_will_change:
            print("No files changed, skipping rsync")
            return []

        print_banner(f"There were {len(files_will_change)} files changed")

        for file in files_will_change:
            print(f"File changed: {file.as_posix()}")

        # Perform the actual sync, this time behind the write lock
        with self.rwlock.write_lock():
            print("Performing code sync and rebuild")
            files_changed = sync_fastled(
                src=src_to_merge_from, dst=FASTLED_SRC, dryrun=False
            )
        if not files_changed:
            print("No files changed after rsync")
            return []

        build_modes = ["debug", "quick", "release"]
        if builds is not None:
            build_modes = builds

        rtn = compile_all_libs(
            FASTLED_SRC.as_posix(),
            "/build",
            build_modes=build_modes,
        )
        if rtn != 0:
            print(f"Error compiling all libs: {rtn}")
            return Exception(f"Error compiling all libs: {rtn}")
        return files_changed
