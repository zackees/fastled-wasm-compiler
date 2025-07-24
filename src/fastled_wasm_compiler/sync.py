import logging
import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor
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
        if len(parts) >= 3 and parts[1] in ["shared", "wasm", "stub", "posix"]:
            return True

        # Otherwise exclude (platforms/arduino/, platforms/esp32/, etc.)
        return False
    except ValueError:
        # File is not relative to src_dir, include it
        return True


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


def _sync_directory(src: Path, dst: Path, dryrun: bool) -> list[Path]:
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
        if files_updated == 0:
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
        # Re-raise the KeyboardInterrupt for the caller to handle
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
        raise

    # Add deleted files to changed list
    changed_files.extend([dst / f for f in files_to_delete])

    return changed_files


def _sync_fastled_examples(src: Path, dst: Path, dryrun: bool = False) -> list[Path]:
    """Sync FastLED examples directory."""
    if src.exists():
        return _sync_directory(src, dst, dryrun)
    return []


def _sync_fastled_src(src: Path, dst: Path, dryrun: bool = False) -> list[Path]:
    """Sync FastLED source directory - now simplified to sync entire src with extension filtering."""
    print(f"Syncing FastLED source from {src} to {dst}")
    changed_files = _sync_directory(src, dst, dryrun)

    if changed_files:
        print(f"Changed files: {len(changed_files)}")
        for changed_file in changed_files[:10]:  # Show first 10 for brevity
            print(f"  {changed_file}")
        if len(changed_files) > 10:
            print(f"  ... and {len(changed_files) - 10} more files")

    return changed_files


def sync_fastled(
    src: Path,
    dst: Path,
    dryrun: bool = False,
    sync_examples: bool = True,
    update_timestamps: bool | None = None,
) -> list[Path]:
    """Sync the source directory to the destination directory using fast Unix tools."""
    start = time.time()

    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)

    # Sync the main source directory
    changed = _sync_fastled_src(src, dst, dryrun=dryrun)

    # Sync examples if requested
    if sync_examples:
        src_examples = src.parent / "examples"
        dst_examples = dst.parent / "examples"
        if src_examples.exists():
            _sync_fastled_examples(src_examples, dst_examples, dryrun=dryrun)
        else:
            src_examples = src / "examples"
            dst_examples = dst / "examples"
            if src_examples.exists():
                _sync_fastled_examples(src_examples, dst_examples, dryrun=dryrun)
            else:
                # Check for Blink example
                src_examples_blink = src / "Blink"
                dst_examples_blink = dst / "Blink"
                if src_examples_blink.exists():
                    _sync_fastled_examples(
                        src_examples_blink, dst_examples_blink, dryrun=dryrun
                    )

    elapsed = time.time() - start
    print(f"Fast sync from {src} to {dst} complete in {elapsed:.2f} seconds")

    # Update source timestamp after successful sync (only if changes were made and timestamps are enabled)
    if changed:
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
                    f"Updating source timestamp via sync for {len(changed)} changed files",
                    None,
                )
                timestamp_manager.update_source_timestamp()
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not update source timestamp: {e}")

    return changed
