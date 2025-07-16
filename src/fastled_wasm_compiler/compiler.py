import os
import time
from dataclasses import dataclass
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile_all_libs import BuildResult, compile_all_libs
from fastled_wasm_compiler.paths import BUILD_ROOT, FASTLED_SRC, VOLUME_MAPPED_SRC
from fastled_wasm_compiler.print_banner import print_banner
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args
from fastled_wasm_compiler.sync import sync_fastled

_RW_LOCK = fasteners.ReaderWriterLock()


@dataclass
class UpdateSrcResult:
    files_changed: list[Path]
    stdout: str
    error: Exception | None


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

    def _check_and_delete_libraries(self, build_modes: list[str], reason: str) -> None:
        """Check for and delete existing libfastled.a files for the specified build modes.

        Args:
            build_modes: List of build modes to check ("debug", "quick", "release")
            reason: Reason for deletion (for logging)
        """
        for mode in build_modes:
            lib_path = BUILD_ROOT / mode / "libfastled.a"
            if lib_path.exists():
                print(f"Deleting existing library {lib_path} ({reason})")
                try:
                    lib_path.unlink()
                    print(f"✓ Successfully deleted {lib_path}")
                except OSError as e:
                    print(f"⚠️  Warning: Could not delete {lib_path}: {e}")
            else:
                print(f"Library {lib_path} does not exist, nothing to delete")

    def _check_missing_libraries(self, build_modes: list[str]) -> list[str]:
        """Check which libfastled.a files are missing for the specified build modes.

        Args:
            build_modes: List of build modes to check ("debug", "quick", "release")

        Returns:
            List of build modes that are missing their libfastled.a files
        """
        missing_modes = []
        for mode in build_modes:
            lib_path = BUILD_ROOT / mode / "libfastled.a"
            if not lib_path.exists():
                missing_modes.append(mode)
                print(f"⚠️  Missing library: {lib_path}")
            else:
                lib_size = lib_path.stat().st_size
                print(f"✓ Found library: {lib_path} ({lib_size} bytes)")
        return missing_modes

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
    ) -> UpdateSrcResult | Exception:
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
                msg = f"Skipping fastled src update: no source directory in {src_to_merge_from}"
                print(msg)
                # return []  # Nothing to do
                return UpdateSrcResult(
                    files_changed=[],
                    stdout=msg,
                    error=None,
                )

            if not (src_to_merge_from / "FastLED.h").exists():
                error_msg = f"FastLED.h not found in {src_to_merge_from}"
                print_banner(f"Error: {error_msg}")
                return FileNotFoundError(error_msg)

            # Determine build modes - use the modes specified during initialization
            build_modes = builds if builds is not None else self.build_libs

            # Check for missing libraries and force recompile if any are missing
            missing_modes = self._check_missing_libraries(build_modes)
            force_recompile = len(missing_modes) > 0
            if force_recompile:
                print_banner(f"Missing libraries detected for modes: {missing_modes}")
                print("Forcing recompilation of all libraries")

            # First check what files will change
            files_will_change: list[Path] = sync_fastled(
                src=src_to_merge_from, dst=FASTLED_SRC, dryrun=True
            )

            # If no files will change and no libraries are missing, skip everything
            if not files_will_change and not force_recompile:
                print(
                    "No files changed and all libraries present, skipping sync and rebuild"
                )
                # return []
                return UpdateSrcResult(
                    files_changed=[],
                    stdout="No files changed and all libraries present, skipping sync and rebuild",
                    error=None,
                )

            # If files will change, show what changed
            if files_will_change:
                print_banner(f"There were {len(files_will_change)} files changed")
                for file in files_will_change:
                    print(f"File changed: {file.as_posix()}")

                # Delete existing libraries when files have changed
                self._check_and_delete_libraries(build_modes, "source files changed")

                # Perform the actual sync, this time behind the write lock
                with self.rwlock.write_lock():
                    print("Performing code sync and rebuild")
                    files_changed = sync_fastled(
                        src=src_to_merge_from, dst=FASTLED_SRC, dryrun=False
                    )

                if not files_changed:
                    msg = "No files changed after sync and rebuild, but files were expected to change"
                    print(msg)
                    return UpdateSrcResult(
                        files_changed=[],
                        stdout="msg",
                        error=None,
                    )
            else:
                # If we reach here, force_recompile is True but no files changed
                # We still need to compile because libraries are missing
                files_changed = []
                print(
                    "No source files changed, but recompiling due to missing libraries"
                )

            # Compile the libraries (either because files changed or libraries are missing)
            print_banner("Compiling libraries with updated source...")
            result: BuildResult = compile_all_libs(
                FASTLED_SRC.as_posix(),
                str(BUILD_ROOT),
                build_modes=build_modes,
            )

            if result.return_code != 0:
                error_msg = (
                    f"Failed to compile libraries with exit code: {result.return_code}"
                )
                stdout = result.stdout
                print_banner(f"Error: {stdout}")
                return RuntimeError(stdout)

            # Verify the build output
            for mode in build_modes:
                lib_path = BUILD_ROOT / mode / "libfastled.a"
                if not lib_path.exists():
                    error_msg = f"Expected library not found at {lib_path}"
                    print_banner(f"Error: {error_msg}")
                    return FileNotFoundError(error_msg)

            print_banner("Library compilation completed successfully")
            return UpdateSrcResult(
                files_changed=files_changed,
                stdout="Library compilation completed successfully",
                error=None,
            )

        except Exception as e:
            error_msg = f"Unexpected error during source update: {str(e)}"
            print_banner(f"Error: {error_msg}")
            return RuntimeError(error_msg)
