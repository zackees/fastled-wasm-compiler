import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import fasteners

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compile_all_libs import (
    BuildResult,
    compile_all_libs,
)
from fastled_wasm_compiler.paths import (
    BUILD_ROOT,
    FASTLED_SRC,
    VOLUME_MAPPED_SRC,
    can_use_thin_lto,
)
from fastled_wasm_compiler.print_banner import print_banner
from fastled_wasm_compiler.run_compile import run_compile as run_compiler_with_args
from fastled_wasm_compiler.sync import sync_fastled

_RW_LOCK = fasteners.ReaderWriterLock()


@dataclass
class UpdateSrcResult:
    """Result from updating source directory."""

    files_changed: list[Path]
    stdout: str
    error: Exception | None


@dataclass
class LibraryBackup:
    """Backup information for a library file."""

    original_path: Path
    backup_path: Path
    archive_type: str
    build_mode: str


class CompilerImpl:

    def __init__(
        self,
        volume_mapped_src: Path | None = None,
        build_libs: list[str] | None = None,
        thin_lto: bool = True,
    ) -> None:
        # At this time we always use exclusive locks, but want
        # to keep the reader/writer lock for future use
        self.volume_mapped_src: Path = (
            volume_mapped_src if volume_mapped_src else VOLUME_MAPPED_SRC
        )
        self.rwlock = _RW_LOCK
        # Default to all modes if none specified
        self.build_libs = build_libs if build_libs else ["debug", "quick", "release"]
        self.thin_lto = thin_lto
        self._library_backups: list[LibraryBackup] = []
        self._backup_temp_dir: Path | None = None

    def _create_backup_directory(self) -> Path:
        """Create a temporary directory for library backups.

        Returns:
            Path to the backup directory
        """
        if self._backup_temp_dir is None:
            self._backup_temp_dir = Path(tempfile.mkdtemp(prefix="libfastled_backup_"))
            print(f"📁 Created backup directory: {self._backup_temp_dir}")
        return self._backup_temp_dir

    def _backup_and_delete_libraries(self, build_modes: list[str], reason: str) -> None:
        """Backup existing libfastled.a files to temp directory, then delete originals.

        Args:
            build_modes: List of build modes to check ("debug", "quick", "release")
            reason: Reason for deletion (for logging)
        """
        # Clear any existing backups
        self._clear_library_backups()

        for mode in build_modes:
            # Check for both thin and regular archives - backup whichever exists
            thin_lib_path = BUILD_ROOT / mode / "libfastled-thin.a"
            regular_lib_path = BUILD_ROOT / mode / "libfastled.a"

            # Determine which library files actually exist and backup them
            libs_to_backup = []
            if thin_lib_path.exists():
                libs_to_backup.append((thin_lib_path, "thin"))
            if regular_lib_path.exists():
                libs_to_backup.append((regular_lib_path, "regular"))

            for lib_path, archive_type in libs_to_backup:
                # Create backup directory if needed
                backup_dir = self._create_backup_directory()

                # Create backup file path with mode and archive type
                backup_filename = f"{mode}_{archive_type}_libfastled.a"
                backup_path = backup_dir / backup_filename

                print(
                    f"💾 Backing up {archive_type} library {lib_path} to {backup_path} ({reason})"
                )
                try:
                    # Copy the file to backup location
                    shutil.copy2(lib_path, backup_path)

                    # Store backup info
                    backup_info = LibraryBackup(
                        original_path=lib_path,
                        backup_path=backup_path,
                        archive_type=archive_type,
                        build_mode=mode,
                    )
                    self._library_backups.append(backup_info)

                    # Now delete the original
                    lib_path.unlink()
                    print(f"✓ Successfully backed up and deleted {lib_path}")

                except (OSError, shutil.Error) as e:
                    print(f"⚠️  Warning: Could not backup {lib_path}: {e}")
                    # If backup failed, don't delete the original
                    continue

            # Log if no libraries were found to backup for this mode
            if not libs_to_backup:
                print(f"No library files found for mode {mode}, nothing to backup")

            # Delete PCH files to prevent staleness issues
            build_dir = BUILD_ROOT / mode
            pch_files = [
                build_dir / "fastled_pch.h",  # PCH source header
                build_dir / "fastled_pch.h.gch",  # Compiled PCH cache
            ]

            for pch_file in pch_files:
                if pch_file.exists():
                    print(f"Deleting stale PCH file {pch_file} ({reason})")
                    try:
                        # Log PCH file deletion
                        from fastled_wasm_compiler.timestamp_utils import (
                            _log_timestamp_operation,
                        )

                        old_timestamp = pch_file.stat().st_mtime
                        _log_timestamp_operation("DELETE", str(pch_file), old_timestamp)

                        pch_file.unlink()
                        print(f"✓ Successfully deleted {pch_file}")
                    except OSError as e:
                        print(f"⚠️  Warning: Could not delete {pch_file}: {e}")
                else:
                    # Log when PCH file doesn't exist for deletion
                    try:
                        from fastled_wasm_compiler.timestamp_utils import (
                            _log_timestamp_operation,
                        )

                        _log_timestamp_operation(
                            "DELETE", f"{pch_file} (not found)", None
                        )
                    except Exception:
                        pass

    def _restore_library_backups(self) -> None:
        """Restore library files from backup if compilation failed."""
        if not self._library_backups:
            print("📂 No library backups to restore")
            return

        print(
            f"🔄 Restoring {len(self._library_backups)} library backups due to compilation failure..."
        )

        for backup_info in self._library_backups:
            try:
                # Ensure the target directory exists
                backup_info.original_path.parent.mkdir(parents=True, exist_ok=True)

                # Restore the file
                shutil.copy2(backup_info.backup_path, backup_info.original_path)
                print(
                    f"✓ Restored {backup_info.archive_type} library: {backup_info.original_path}"
                )

            except (OSError, shutil.Error) as e:
                print(
                    f"⚠️  Warning: Could not restore backup {backup_info.backup_path}: {e}"
                )

        print("🔄 Library backup restoration complete")

    def _clear_library_backups(self) -> None:
        """Clear library backups and remove temporary backup directory."""
        if self._backup_temp_dir and self._backup_temp_dir.exists():
            try:
                shutil.rmtree(self._backup_temp_dir)
                print(f"🗑️  Cleaned up backup directory: {self._backup_temp_dir}")
            except OSError as e:
                print(
                    f"⚠️  Warning: Could not clean up backup directory {self._backup_temp_dir}: {e}"
                )

        self._backup_temp_dir = None
        self._library_backups.clear()

    def _check_and_delete_libraries(self, build_modes: list[str], reason: str) -> None:
        """Legacy method that now uses the backup mechanism.

        This method is kept for backward compatibility and redirects to the new backup method.

        Args:
            build_modes: List of build modes to check ("debug", "quick", "release")
            reason: Reason for deletion (for logging)
        """
        self._backup_and_delete_libraries(build_modes, reason)

    def _check_missing_libraries(self, build_modes: list[str]) -> list[str]:
        """Check which libfastled.a files are missing for the specified build modes.

        Args:
            build_modes: List of build modes to check ("debug", "quick", "release")

        Returns:
            List of build modes that are missing their expected archive files
        """

        missing_modes = []
        # Use volume mapped source aware archive selection
        use_thin = can_use_thin_lto()

        for mode in build_modes:
            if use_thin:
                # Use thin archives
                lib_path = BUILD_ROOT / mode / "libfastled-thin.a"
                archive_type = "thin"
            else:
                # Use regular archives
                lib_path = BUILD_ROOT / mode / "libfastled.a"
                archive_type = "regular"

            if lib_path.exists():
                lib_size = lib_path.stat().st_size
                print(f"✓ Found {archive_type} library: {lib_path} ({lib_size} bytes)")
            else:
                missing_modes.append(mode)
                print(f"⚠️  Missing {archive_type} library for mode {mode}: {lib_path}")

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

                    # Handle error case - check the error field in UpdateSrcResult
                    if result.error is not None:
                        error_msg = f"Error updating source: {result.error}"
                        print_banner(error_msg)
                        return result.error

                    # Handle success case with changed files
                    if len(result.files_changed) > 0:
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
    ) -> UpdateSrcResult:
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
                return UpdateSrcResult(
                    files_changed=[],
                    stdout=error_msg,
                    error=ValueError(error_msg),
                )

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
                return UpdateSrcResult(
                    files_changed=[],
                    stdout=error_msg,
                    error=FileNotFoundError(error_msg),
                )

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
                        stdout=msg,
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
            # Use centralized archive mode detection and validation
            print_banner("Compiling libraries with updated source...")
            result: BuildResult = compile_all_libs(
                FASTLED_SRC.as_posix(),
                str(BUILD_ROOT),
                build_modes=build_modes,
                # archive_type defaults to None, which uses centralized detection and validation
            )

            if result.return_code != 0:
                # Compilation failed - restore backups before reporting error
                print_banner("Compilation failed - restoring library backups...")
                self._restore_library_backups()

                error_msg = (
                    f"Failed to compile libraries with exit code: {result.return_code}"
                )
                stdout = result.stdout
                print_banner(f"Error: {stdout}")
                return UpdateSrcResult(
                    files_changed=[],
                    stdout=stdout,
                    error=RuntimeError(stdout),
                )

            # Verify the build output - check for expected archive type based on configuration
            from fastled_wasm_compiler.paths import get_expected_archive_path

            for mode in build_modes:
                # Use centralized archive selection to get the expected archive path
                expected_lib = get_expected_archive_path(mode.upper())
                archive_type = "thin" if "thin" in expected_lib.name else "regular"

                if not expected_lib.exists():
                    # Library verification failed - restore backups before reporting error
                    print_banner(
                        "Library verification failed - restoring library backups..."
                    )
                    self._restore_library_backups()

                    error_msg = (
                        f"Expected {archive_type} library not found at {expected_lib}"
                    )
                    print_banner(f"Error: {error_msg}")
                    return UpdateSrcResult(
                        files_changed=[],
                        stdout=error_msg,
                        error=FileNotFoundError(error_msg),
                    )

            print_banner("Library compilation completed successfully")

            # Clean up backups on successful compilation
            self._clear_library_backups()

            return UpdateSrcResult(
                files_changed=files_changed,
                stdout="Library compilation completed successfully",
                error=None,
            )

        except Exception as e:
            # Unexpected error - restore backups before reporting error
            print_banner("Unexpected error occurred - restoring library backups...")
            self._restore_library_backups()

            error_msg = f"Unexpected error during source update: {str(e)}"
            print_banner(f"Error: {error_msg}")
            return UpdateSrcResult(
                files_changed=[],
                stdout=error_msg,
                error=RuntimeError(error_msg),
            )
