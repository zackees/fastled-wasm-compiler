import warnings
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.paths import VOLUME_MAPPED_SRC
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args


class Compiler:

    def __init__(self, volume_mapped_src: Path | None = None) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.volume_mapped_src: Path = (
            volume_mapped_src if volume_mapped_src else VOLUME_MAPPED_SRC
        )
        self.rwlock = fasteners.ReaderWriterLock()

    def compile(self, args: Args) -> int:
        err = self.update_src(self.volume_mapped_src)
        if err:
            warnings.warn(f"Error updating source: {err}")
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

        from fastled_wasm_compiler.code_sync import CodeSync

        code_sync = CodeSync()
        with self.rwlock.write_lock():
            code_sync.update_and_compile_core(src_to_merge_from)
