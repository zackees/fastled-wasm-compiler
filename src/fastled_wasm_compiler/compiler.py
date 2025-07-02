import os
import time
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile_all_libs import compile_all_libs
from fastled_wasm_compiler.paths import FASTLED_SRC, VOLUME_MAPPED_SRC
from fastled_wasm_compiler.print_banner import print_banner
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args
from fastled_wasm_compiler.sync import sync_fastled

_RW_LOCK = fasteners.ReaderWriterLock()


class CompilerImpl:

    def __init__(
        self, volume_mapped_src: Path | None = None, build_libs: list[str] | None = None
    ) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.volume_mapped_src: Path = (
            volume_mapped_src if volume_mapped_src else VOLUME_MAPPED_SRC
        )
        self.rwlock = _RW_LOCK
        # Default to all modes if none specified
        self.build_libs = build_libs if build_libs else ["debug", "quick", "release"]

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
                    result = self.update_src(src_to_merge_from=self.volume_mapped_src)

                    # Handle error case
                    if isinstance(result, Exception):
                        error_msg = f"Error updating source: {result}"
                        print_banner(error_msg)
                        return Exception(error_msg)

                    # Handle success case with changed files
                    if isinstance(result, list) and len(result) > 0:
                        clear_cache = (
                            True  # Always clear cache when the source changes.
                        )
                        diff = time.time() - start
                        print_banner(
                            f"Recompile of static lib(s) source took {diff:.2f} seconds"
                        )
                    # If no files changed (empty list), continue without clearing cache

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

        Returns:
            On success: List of changed files (may be empty if no changes)
            On error: Exception with error details
        """
        try:
            src_to_merge_from = src_to_merge_from or self.volume_mapped_src
            if not isinstance(src_to_merge_from, Path):
                error_msg = (
                    f"src_to_merge_from must be a Path, got {type(src_to_merge_from)}"
                )
                print_banner(f"Error: {error_msg}")
                return ValueError(error_msg)

            if not src_to_merge_from.exists():
                print("Skipping fastled src update: no source directory")
                return []  # Nothing to do

            if not (src_to_merge_from / "FastLED.h").exists():
                error_msg = f"FastLED.h not found in {src_to_merge_from}"
                print_banner(f"Error: {error_msg}")
                return FileNotFoundError(error_msg)

            # First check what files will change
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
                print(
                    "Warning: No files changed after rsync, but files were expected to change"
                )
                return []

            # Determine build modes - use the modes specified during initialization
            build_modes = builds if builds is not None else self.build_libs

            # Compile the libraries
            print_banner("Compiling libraries with updated source...")
            rtn = compile_all_libs(
                FASTLED_SRC.as_posix(),
                "/build",
                build_modes=build_modes,
            )

            if rtn != 0:
                error_msg = f"Failed to compile libraries with exit code: {rtn}"
                print_banner(f"Error: {error_msg}")
                return RuntimeError(error_msg)

            # Verify the build output
            for mode in build_modes:
                lib_path = Path(f"/build/{mode}/libfastled.a")
                if not lib_path.exists():
                    error_msg = f"Expected library not found at {lib_path}"
                    print_banner(f"Error: {error_msg}")
                    return FileNotFoundError(error_msg)

            print_banner("Library compilation completed successfully")
            return files_changed

        except Exception as e:
            error_msg = f"Unexpected error during source update: {str(e)}"
            print_banner(f"Error: {error_msg}")
            return RuntimeError(error_msg)
