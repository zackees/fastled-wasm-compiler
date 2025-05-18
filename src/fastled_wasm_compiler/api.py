from pathlib import Path

import fasteners


class Compiler:

    def __init__(self) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.rwlock = fasteners.ReaderWriterLock()

    def update_src(self, src: Path) -> Exception | None:
        """
        Update the source directory.
        """
        if not (src / "FastLED.h").exists():
            return FileNotFoundError(f"FastLED.h not found in {src}")

        from fastled_wasm_compiler.code_sync import CodeSync

        code_sync = CodeSync()
        with self.rwlock.write_lock():
            code_sync.update_and_compile_core(src)
