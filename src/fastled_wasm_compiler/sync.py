import logging
import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .line_ending_pool import get_line_ending_pool

# Create logger for this module
logger = logging.getLogger(__name__)

_LOGGING_ENABLED = True

# Create formatter with filename and line number
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Set logger level based on _LOGGING_ENABLED flag
if not _LOGGING_ENABLED:
    logger.setLevel(logging.CRITICAL)  # Effectively disables most logging
else:
    logger.setLevel(logging.INFO)


# Allowed file extensions for syncing
ALLOWED_EXTENSIONS = [
    "*.c",
    "*.cc",
    "*.cpp",
    "*.cxx",
    "*.c++",  # C/C++ source files
    "*.h",
    "*.hh",
    "*.hpp",
    "*.hxx",
    "*.h++",  # C/C++ header files
    "*.txt",  # Text files
    "*.js",
    "*.mjs",  # JavaScript files
    "*.html",  # HTML files
    "*.css",  # CSS files
    "*.ini",  # Configuration files
    "*.toml",  # TOML configuration files
]

# Extensions that require library rebuild when changed
LIBRARY_AFFECTING_EXTENSIONS = [
    "*.c",
    "*.cc",
    "*.cpp",
    "*.cxx",
    "*.c++",  # C/C++ source files
    "*.h",
    "*.hh",
    "*.hpp",
    "*.hxx",
    "*.h++",  # C/C++ header files
    "*.txt",  # Text files (may contain build configs)
    "*.ini",  # Configuration files
    "*.toml",  # TOML configuration files
]

# Extensions that are assets only (don't require library rebuild)
ASSET_ONLY_EXTENSIONS = [
    "*.js",
    "*.mjs",  # JavaScript files
    "*.html",  # HTML files
    "*.css",  # CSS files
]


@dataclass
class SyncResult:
    """Result from sync operation with file classification."""

    all_changed_files: list[Path]
    library_affecting_files: list[Path]
    asset_only_files: list[Path]

    def requires_library_rebuild(self) -> bool:
        """Return True if library rebuild is required."""
        return len(self.library_affecting_files) > 0


def _is_library_affecting_file(file_path: Path) -> bool:
    """Check if a file change should trigger library rebuild."""
    for pattern in LIBRARY_AFFECTING_EXTENSIONS:
        if file_path.match(pattern):
            return True
    return False


def _is_asset_only_file(file_path: Path) -> bool:
    """Check if a file is an asset that doesn't affect library compilation."""
    for pattern in ASSET_ONLY_EXTENSIONS:
        if file_path.match(pattern):
            return True
    return False


def _find_files_with_extensions(src_dir: Path) -> list[Path]:
    """Use Unix find command to quickly discover files with allowed extensions and apply platforms filtering."""
    if not src_dir.exists():
        return []

    # Build find command with extension filters
    find_cmd = ["find", str(src_dir), "-type", "f"]

    # Add platforms directory filtering:
    # Include: files NOT in platforms/, OR files in platforms/shared/, platforms/wasm/, platforms/stub/, OR files directly in platforms/
    find_cmd.extend(
        [
            "(",
            # Files not under platforms/ at all
            "-not",
            "-path",
            "*/platforms/*",
            "-o",
            # Files directly in platforms/ (not in subdirectories)
            "-path",
            "*/platforms/*",
            "-not",
            "-path",
            "*/platforms/*/*",
            "-o",
            # Files in allowed platform subdirectories
            "-path",
            "*/platforms/shared/*",
            "-o",
            "-path",
            "*/platforms/wasm/*",
            "-o",
            "-path",
            "*/platforms/stub/*",
            "-o",
            "-path",
            "*/platforms/posix/*",
            "-o",
            "-path",
            "*/platforms/arm/*",
            ")",
        ]
    )

    # Add extension filters using -name patterns
    if ALLOWED_EXTENSIONS:
        find_cmd.extend(["-a", "("])
        for i, ext in enumerate(ALLOWED_EXTENSIONS):
            if i > 0:
                find_cmd.append("-o")
            find_cmd.extend(["-name", ext])
        find_cmd.append(")")

    try:
        result = subprocess.run(find_cmd, capture_output=True, text=True, check=True)

        # Convert output lines to Path objects
        files = []
        for line in result.stdout.strip().split("\n"):
            if line:  # Skip empty lines
                files.append(Path(line))

        return files
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Fallback to Python if find command fails or not available (Windows)
        logger.warning(f"Find command failed ({e}), falling back to Python scanning")
        return _find_files_python_fallback(src_dir)


def _should_include_platforms_path(file_path: Path, src_dir: Path) -> bool:
    """Check if a file in platforms directory should be included based on filtering rules."""
    try:
        rel_path = file_path.relative_to(src_dir)
        parts = rel_path.parts

        # If not in platforms directory, include it
        if len(parts) == 0 or parts[0] != "platforms":
            return True

        # If directly in platforms/ (not in subdirectory), include it
        if len(parts) == 2:  # platforms/filename
            return True

        # If in allowed subdirectories, include it
        if len(parts) >= 3 and parts[1] in ["shared", "wasm", "stub", "posix", "arm"]:
            return True

        # Otherwise exclude (platforms/arduino/, platforms/esp32/, etc.)
        return False
    except ValueError:
        # File is not relative to src_dir, include it
        return True


def _sync_web_assets_with_rsync(src: Path, dst: Path, dryrun: bool) -> SyncResult:
    """
    Sync web assets (*.js, *.css, *.html) using rsync for simplicity.
    This bypasses change detection and always syncs, allowing deletions.
    """
    if not src.exists():
        return SyncResult(
            all_changed_files=[], library_affecting_files=[], asset_only_files=[]
        )

    if not dst.exists():
        if not dryrun:
            dst.mkdir(parents=True, exist_ok=True)

    # Build rsync command for web assets only
    # Include only the extensions we want to sync unconditionally
    rsync_cmd = [
        "rsync",
        "-av",
        "--delete",
        "--include=*.js",
        "--include=*.mjs",
        "--include=*.css",
        "--include=*.html",
        "--include=*/",  # Include directories
        "--exclude=*",  # Exclude everything else
        f"{src}/",
        f"{dst}/",
    ]

    try:
        changed_files = []

        if not dryrun:
            result = subprocess.run(
                rsync_cmd, capture_output=True, text=True, check=True
            )
            print(f"Rsync web assets from {src} to {dst}")

            # Parse rsync output to identify actually changed files
            # Rsync with -v outputs changed files one per line
            # Skip directory entries (ending with /) and metadata lines
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    # Skip empty lines, directory markers, and rsync metadata
                    if (
                        not line
                        or line.endswith("/")
                        or line.startswith("sending")
                        or line.startswith("sent")
                        or line.startswith("total")
                    ):
                        continue
                    # Check if this is a file with one of our extensions
                    if any(
                        line.endswith(ext.replace("*", ""))
                        for ext in ["*.js", "*.mjs", "*.css", "*.html"]
                    ):
                        changed_file = dst / line
                        if changed_file.exists():
                            changed_files.append(changed_file)

                if changed_files:
                    print(f"Rsync updated {len(changed_files)} web asset file(s)")
        else:
            print(f"[DRY RUN] Would rsync web assets from {src} to {dst}")
            # In dry run mode, scan for all web assets as potential changes
            for pattern in ["*.js", "*.mjs", "*.css", "*.html"]:
                changed_files.extend(dst.rglob(pattern))

        return SyncResult(
            all_changed_files=changed_files,
            library_affecting_files=[],  # Web assets never affect library
            asset_only_files=changed_files,
        )

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Rsync command failed ({e}), falling back to regular sync")
        # Fall back to regular sync if rsync fails, but filter to only web assets
        return _sync_web_assets_manual(src, dst, dryrun)


def _sync_web_assets_manual(src: Path, dst: Path, dryrun: bool) -> SyncResult:
    """
    Manual sync for web assets when rsync is not available.
    Only syncs *.js, *.mjs, *.css, *.html files and handles deletions.
    """
    if not src.exists():
        return SyncResult(
            all_changed_files=[], library_affecting_files=[], asset_only_files=[]
        )

    if not dst.exists():
        if not dryrun:
            dst.mkdir(parents=True, exist_ok=True)

    web_extensions = ["*.js", "*.mjs", "*.css", "*.html"]
    changed_files = []

    # Find all web asset files in source
    src_web_files = []
    for pattern in web_extensions:
        src_web_files.extend(src.rglob(pattern))

    # Convert to relative paths for tracking
    src_relative = {f.relative_to(src) for f in src_web_files}

    # Find existing web asset files in destination
    dst_web_files = []
    if dst.exists():
        for pattern in web_extensions:
            dst_web_files.extend(dst.rglob(pattern))

    dst_relative = {f.relative_to(dst) for f in dst_web_files}

    # Copy new/changed files
    for rel_file in src_relative:
        src_file = src / rel_file
        dst_file = dst / rel_file

        # Create parent directory if needed
        if not dryrun and not dst_file.parent.exists():
            dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Always copy (unconditional sync)
        if not dryrun:
            import shutil

            shutil.copy2(src_file, dst_file)

        changed_files.append(dst_file)
        print(f"  Updated (asset): {rel_file}")

    # Delete files that no longer exist in source
    files_to_delete = dst_relative - src_relative
    for rel_file in files_to_delete:
        dst_file = dst / rel_file
        if dst_file.exists() and not dryrun:
            dst_file.unlink()
        print(f"  Deleted (asset): {rel_file}")

    print(
        f"Manual web assets sync: {len(changed_files)} files synced, {len(files_to_delete)} files deleted"
    )

    return SyncResult(
        all_changed_files=changed_files,
        library_affecting_files=[],  # Web assets never affect library
        asset_only_files=changed_files,
    )


def _find_files_python_fallback(src_dir: Path) -> list[Path]:
    """Fallback Python implementation with platforms filtering when find command is not available."""
    files = []
    for file_path in src_dir.rglob("*"):
        if file_path.is_file():
            # Apply platforms directory filtering
            if not _should_include_platforms_path(file_path, src_dir):
                continue

            # Check if file matches any allowed extension
            for pattern in ALLOWED_EXTENSIONS:
                if file_path.match(pattern):
                    files.append(file_path)
                    break
    return files


def _sync_directory(src: Path, dst: Path, dryrun: bool) -> SyncResult:
    """Sync a directory using fast Unix find command for file discovery."""
    assert src.is_dir(), f"Source {src} is not a directory"

    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)

    # Use fast Unix find command to get source files
    src_files = _find_files_with_extensions(src)

    # Get destination files using the same method
    dst_files = _find_files_with_extensions(dst)

    # Convert to relative paths for comparison
    src_relative = {f.relative_to(src) for f in src_files}
    dst_relative = {f.relative_to(dst) for f in dst_files}

    # Create missing directories
    missing_parents_set: set[Path] = set()
    for rel_file in src_relative:
        file_dst = dst / rel_file
        if not file_dst.parent.exists():
            missing_parents_set.add(file_dst.parent)

    # Create directories in one pass
    for dir_path in missing_parents_set:
        if not dryrun:
            dir_path.mkdir(parents=True, exist_ok=True)

    # Files to delete from destination (no longer in source)
    files_to_delete = dst_relative - src_relative

    # Debug output for deletion
    if files_to_delete:
        print(f"Files to delete from destination: {len(files_to_delete)}")
        for file in files_to_delete:
            print(f"  Deleting: {file}")

    changed_files: list[Path] = []

    # Submit all files for line ending conversion and copying (parallel I/O and processing)
    line_ending_futures = {}  # rel_file -> future for line ending conversion

    for rel_file in src_relative:
        src_file = src / rel_file
        dst_file = dst / rel_file
        # Submit file for line ending conversion and copying (worker handles everything)
        future = get_line_ending_pool().convert_file_line_endings_async(
            src_file, dst_file
        )
        line_ending_futures[rel_file] = future

    # Wait for all line ending conversions and file operations to complete
    print(
        f"  Processing {len(line_ending_futures)} files with line ending conversion..."
    )
    files_processed = 0
    files_updated = 0
    files_unchanged = 0
    library_affecting_files = []
    asset_only_files = []

    try:
        for rel_file, future in line_ending_futures.items():
            try:
                result = future.result()
                files_processed += 1

                if isinstance(result, Exception):
                    # Error occurred, log it but continue
                    logger.error(f"Error processing {rel_file}: {result}")
                elif isinstance(result, bool):
                    if result:
                        # File was different and updated
                        dst_file = dst / rel_file
                        changed_files.append(dst_file)
                        files_updated += 1

                        # Classify the changed file
                        if _is_library_affecting_file(rel_file):
                            library_affecting_files.append(dst_file)
                            print(f"  Updated (lib): {rel_file}")
                        elif _is_asset_only_file(rel_file):
                            asset_only_files.append(dst_file)
                            print(f"  Updated (asset): {rel_file}")
                        else:
                            print(f"  Updated: {rel_file}")
                    else:
                        # Files were same, no action needed
                        files_unchanged += 1
                else:
                    logger.warning(
                        f"Unexpected result type for {rel_file}: {type(result)}"
                    )

            except Exception as e:
                logger.error(f"Exception getting result for {rel_file}: {e}")

        # Log summary of processing results
        print(
            f"  Summary: {files_processed} files processed, {files_updated} updated, {files_unchanged} unchanged"
        )
        if len(library_affecting_files) > 0:
            print(
                f"  {len(library_affecting_files)} library-affecting files changed - libfastled will be rebuilt"
            )
        elif len(asset_only_files) > 0:
            print(
                f"  {len(asset_only_files)} asset-only files changed - libfastled recompilation will be skipped"
            )
        elif files_updated == 0:
            print(
                "  No files were updated - libfastled recompilation will be suppressed if libraries exist"
            )

    except KeyboardInterrupt:
        logger.info(
            "Received KeyboardInterrupt during line ending conversion, shutting down gracefully..."
        )
        # Cancel remaining futures
        for remaining_file, remaining_future in line_ending_futures.items():
            if not remaining_future.done():
                remaining_future.cancel()
        # Shutdown the process pool
        # The line_ending_pool is now a global singleton, no explicit shutdown needed here
        # _line_ending_pool.shutdown()

        # Properly interrupt the main thread
        import _thread

        _thread.interrupt_main()
        raise
    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        raise

    # The old file processing logic is no longer needed since workers handle everything
    # Just need to handle file deletions now

    # Delete obsolete files in parallel
    try:
        with ThreadPoolExecutor(max_workers=32) as executor:
            deletion_futures: list[Future] = []

            for rel_file in files_to_delete:
                dst_file = dst / rel_file

                def task_remove(file_dst: Path = dst_file) -> bool:
                    if not dryrun:
                        if file_dst.exists():
                            file_dst.unlink()
                    return True

                future = executor.submit(task_remove)
                deletion_futures.append(future)

            # Wait for deletions to complete
            for future in deletion_futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error deleting file: {e}")

    except KeyboardInterrupt:
        logger.info(
            "Received KeyboardInterrupt during file deletion, shutting down gracefully..."
        )
        # The ThreadPoolExecutor context manager will handle cleanup
        # Properly interrupt the main thread
        import _thread

        _thread.interrupt_main()
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file deletion: {e}")
        raise

    # Add deleted files to changed list (deleted files don't affect library rebuild)
    changed_files.extend([dst / f for f in files_to_delete])

    return SyncResult(
        all_changed_files=changed_files,
        library_affecting_files=library_affecting_files,
        asset_only_files=asset_only_files,
    )


def _sync_fastled_examples(src: Path, dst: Path, dryrun: bool = False) -> SyncResult:
    """Sync FastLED examples directory."""
    if src.exists():
        return _sync_directory(src, dst, dryrun)
    return SyncResult(
        all_changed_files=[], library_affecting_files=[], asset_only_files=[]
    )


def _sync_fastled_src(src: Path, dst: Path, dryrun: bool = False) -> SyncResult:
    """Sync FastLED source directory with special handling for web assets."""
    print(f"Syncing FastLED source from {src} to {dst}")

    # Check if there's a platforms/wasm/compiler directory for web assets
    web_assets_src = src / "platforms" / "wasm" / "compiler"
    web_assets_dst = dst / "platforms" / "wasm" / "compiler"

    if web_assets_src.exists():
        print("Found platforms/wasm/compiler - using rsync for web assets")
        # Sync web assets with rsync first
        web_assets_result = _sync_web_assets_with_rsync(
            web_assets_src, web_assets_dst, dryrun
        )

        # Sync everything else using regular sync
        sync_result = _sync_directory(src, dst, dryrun)

        # Merge results, but avoid double-counting web asset files
        # Remove web asset files from the regular sync result to avoid duplicates
        filtered_all_files = []
        filtered_asset_files = []

        for file_path in sync_result.all_changed_files:
            try:
                rel_path = file_path.relative_to(dst)
                if rel_path.parts[:3] == ("platforms", "wasm", "compiler") and any(
                    file_path.match(pattern)
                    for pattern in ["*.js", "*.mjs", "*.css", "*.html"]
                ):
                    # Skip - this was handled by rsync
                    continue
                else:
                    filtered_all_files.append(file_path)
            except ValueError:
                # File not relative to dst, keep it
                filtered_all_files.append(file_path)

        for file_path in sync_result.asset_only_files:
            try:
                rel_path = file_path.relative_to(dst)
                if rel_path.parts[:3] == ("platforms", "wasm", "compiler") and any(
                    file_path.match(pattern)
                    for pattern in ["*.js", "*.mjs", "*.css", "*.html"]
                ):
                    # Skip - this was handled by rsync
                    continue
                else:
                    filtered_asset_files.append(file_path)
            except ValueError:
                # File not relative to dst, keep it
                filtered_asset_files.append(file_path)

        # Combine results
        combined_result = SyncResult(
            all_changed_files=filtered_all_files + web_assets_result.all_changed_files,
            library_affecting_files=sync_result.library_affecting_files
            + web_assets_result.library_affecting_files,
            asset_only_files=filtered_asset_files + web_assets_result.asset_only_files,
        )
    else:
        # No web assets directory, use regular sync
        combined_result = _sync_directory(src, dst, dryrun)

    if combined_result.all_changed_files:
        print(f"Changed files: {len(combined_result.all_changed_files)}")
        for changed_file in combined_result.all_changed_files[
            :10
        ]:  # Show first 10 for brevity
            print(f"  {changed_file}")
        if len(combined_result.all_changed_files) > 10:
            print(f"  ... and {len(combined_result.all_changed_files) - 10} more files")

    return combined_result


def sync_fastled(
    src: Path,
    dst: Path,
    dryrun: bool = False,
    sync_examples: bool = True,
    update_timestamps: bool | None = None,
) -> SyncResult:
    """Sync the source directory to the destination directory with detailed file classification."""
    start = time.time()

    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)

    # Sync the main source directory
    sync_result = _sync_fastled_src(src, dst, dryrun=dryrun)

    # Sync examples if requested (examples don't typically affect library rebuild)
    if sync_examples:
        src_examples = src.parent / "examples"
        dst_examples = dst.parent / "examples"
        if src_examples.exists():
            examples_result = _sync_fastled_examples(
                src_examples, dst_examples, dryrun=dryrun
            )
            sync_result.all_changed_files.extend(examples_result.all_changed_files)
            sync_result.library_affecting_files.extend(
                examples_result.library_affecting_files
            )
            sync_result.asset_only_files.extend(examples_result.asset_only_files)
        else:
            src_examples = src / "examples"
            dst_examples = dst / "examples"
            if src_examples.exists():
                examples_result = _sync_fastled_examples(
                    src_examples, dst_examples, dryrun=dryrun
                )
                sync_result.all_changed_files.extend(examples_result.all_changed_files)
                sync_result.library_affecting_files.extend(
                    examples_result.library_affecting_files
                )
                sync_result.asset_only_files.extend(examples_result.asset_only_files)
            else:
                # Check for Blink example
                src_examples_blink = src / "Blink"
                dst_examples_blink = dst / "Blink"
                if src_examples_blink.exists():
                    examples_result = _sync_fastled_examples(
                        src_examples_blink, dst_examples_blink, dryrun=dryrun
                    )
                    sync_result.all_changed_files.extend(
                        examples_result.all_changed_files
                    )
                    sync_result.library_affecting_files.extend(
                        examples_result.library_affecting_files
                    )
                    sync_result.asset_only_files.extend(
                        examples_result.asset_only_files
                    )

    elapsed = time.time() - start
    print(f"Fast sync from {src} to {dst} complete in {elapsed:.2f} seconds")

    # Update source timestamp after successful sync (only if library-affecting changes were made)
    if sync_result.requires_library_rebuild():
        # Determine if we should update timestamps
        should_update = update_timestamps
        if should_update is None:
            # Auto-detect if we're in a Docker environment or if /git exists
            docker_git_root = Path("/git")
            should_update = docker_git_root.exists() and docker_git_root.is_dir()

        if should_update:
            try:
                from fastled_wasm_compiler.timestamp_utils import (
                    _log_timestamp_operation,
                    get_timestamp_manager,
                )

                timestamp_manager = get_timestamp_manager()
                _log_timestamp_operation(
                    "SYNC_UPDATE",
                    f"Updating source timestamp via sync for {len(sync_result.library_affecting_files)} library-affecting changed files",
                    None,
                )
                timestamp_manager.update_source_timestamp()
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not update source timestamp: {e}")

    return sync_result
