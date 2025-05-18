from pathlib import Path

import fasteners

from fastled_wasm_compiler.paths import VOLUME_MAPPED_SRC


class Compiler:

    def __init__(self, volume_mapped_src: Path | None = None) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.volume_mapped_src = volume_mapped_src
        self.rwlock = fasteners.ReaderWriterLock()

    def update_src(self, src_to_merge_from: Path | None = None) -> Exception | None:
        """
        Update the source directory.
        """

        if src_to_merge_from is not None:
            if not src_to_merge_from.exists():
                return FileNotFoundError(
                    f"Source directory {src_to_merge_from} does not exist"
                )
        elif self.volume_mapped_src is not None:
            if not self.volume_mapped_src.exists():
                return FileNotFoundError(
                    f"Volume mapped source directory {self.volume_mapped_src} does not exist"
                )
            src_to_merge_from = self.volume_mapped_src
        else:
            if not VOLUME_MAPPED_SRC.exists():
                return FileNotFoundError(
                    f"Volume mapped source directory {VOLUME_MAPPED_SRC} does not exist"
                )
            src_to_merge_from = VOLUME_MAPPED_SRC

        if not (src_to_merge_from / "FastLED.h").exists():
            return FileNotFoundError(f"FastLED.h not found in {src_to_merge_from}")

        from fastled_wasm_compiler.code_sync import CodeSync

        code_sync = CodeSync()
        with self.rwlock.write_lock():
            code_sync.update_and_compile_core(src_to_merge_from)
