"""
Timestamp utilities for tracking source updates and library builds.

This module provides functionality to track when FastLED source is updated
and when libfastled libraries are built, enabling lazy rebuilds.
"""

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class TimestampManager:
    """Manages timestamps for source updates and library builds."""

    def __init__(self, git_root: Path = Path("/git")) -> None:
        """Initialize timestamp manager.

        Args:
            git_root: Root directory where FastLED source is located
        """
        self.git_root = git_root
        self.timestamp_dir = git_root / ".timestamps"
        self.source_timestamp_file = self.timestamp_dir / "source_update.timestamp"

    def _ensure_timestamp_dir(self) -> None:
        """Ensure the timestamp directory exists."""
        self.timestamp_dir.mkdir(parents=True, exist_ok=True)

    def update_source_timestamp(self) -> None:
        """Update the source timestamp file with current time."""
        self._ensure_timestamp_dir()
        current_time = time.time()
        self.source_timestamp_file.write_text(str(current_time))
        print(f"📅 Source timestamp updated: {self.source_timestamp_file}")

    def get_source_timestamp(self) -> float | None:
        """Get the source update timestamp.

        Returns:
            Source timestamp as float, or None if not found
        """
        if not self.source_timestamp_file.exists():
            return None
        try:
            return float(self.source_timestamp_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def get_library_timestamp(
        self, build_mode: str, archive_type: str = "thin"
    ) -> float | None:
        """Get the library build timestamp for a specific build mode.

        Args:
            build_mode: Build mode (debug, quick, release)
            archive_type: Archive type (thin or regular)

        Returns:
            Library timestamp as float, or None if not found
        """
        build_root = Path("/build")
        if archive_type == "thin":
            lib_file = build_root / build_mode.lower() / "libfastled-thin.a"
        else:
            lib_file = build_root / build_mode.lower() / "libfastled.a"

        if not lib_file.exists():
            return None

        try:
            return lib_file.stat().st_mtime
        except OSError:
            return None

    def should_rebuild_library(
        self, build_mode: str, archive_type: str = "thin"
    ) -> bool:
        """Check if library should be rebuilt based on timestamp comparison.

        Args:
            build_mode: Build mode (debug, quick, release)
            archive_type: Archive type (thin or regular)

        Returns:
            True if library should be rebuilt, False otherwise
        """
        source_time = self.get_source_timestamp()
        if source_time is None:
            # No source timestamp, assume rebuild needed
            print(f"🔄 No source timestamp found, rebuild needed for {build_mode}")
            return True

        lib_time = self.get_library_timestamp(build_mode, archive_type)
        if lib_time is None:
            # No library found, rebuild needed
            print(
                f"🔄 No library found, rebuild needed for {build_mode} ({archive_type})"
            )
            return True

        if source_time > lib_time:
            # Source is newer than library, rebuild needed
            print(
                f"🔄 Source newer than library, rebuild needed for {build_mode} ({archive_type})"
            )
            print(f"   Source time: {time.ctime(source_time)}")
            print(f"   Library time: {time.ctime(lib_time)}")
            return True
        else:
            # Library is up to date
            print(f"✅ Library up to date for {build_mode} ({archive_type})")
            print(f"   Source time: {time.ctime(source_time)}")
            print(f"   Library time: {time.ctime(lib_time)}")
            return False


def get_timestamp_manager(git_root: Path | None = None) -> TimestampManager:
    """Get a configured timestamp manager instance.

    Args:
        git_root: Optional git root path, defaults to /git

    Returns:
        TimestampManager instance
    """
    if git_root is None:
        git_root = Path("/git")
    return TimestampManager(git_root)
