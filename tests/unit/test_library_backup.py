"""Tests for library backup mechanism in compiler.py."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastled_wasm_compiler.compiler import CompilerImpl


class TestLibraryBackup:
    """Test the library backup and restore mechanism."""

    def setup_method(self) -> None:
        """Set up test environment with temporary directories."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.build_root = self.temp_dir / "build"
        self.volume_src = self.temp_dir / "volume_src"

        # Create directory structure
        self.build_root.mkdir(parents=True)
        self.volume_src.mkdir(parents=True)

        # Create mock library files
        for mode in ["debug", "quick", "release"]:
            mode_dir = self.build_root / mode
            mode_dir.mkdir(parents=True)

            # Create both thin and regular library files
            regular_lib = mode_dir / "libfastled.a"
            thin_lib = mode_dir / "libfastled-thin.a"

            regular_lib.write_text(f"Mock {mode} regular library content")
            thin_lib.write_text(f"Mock {mode} thin library content")

    def teardown_method(self) -> None:
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_backup_creation(self) -> None:
        """Test that backup directory and files are created correctly."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # Create backups
            compiler._backup_and_delete_libraries(["debug", "quick"], "test backup")

            # Verify backup directory was created
            assert compiler._backup_temp_dir is not None
            assert compiler._backup_temp_dir.exists()

            # Verify backup files were created (2 modes × 2 archive types = 4 backups)
            assert len(compiler._library_backups) == 4

            # Verify all backups are valid
            build_modes = {backup.build_mode for backup in compiler._library_backups}
            archive_types = {
                backup.archive_type for backup in compiler._library_backups
            }

            assert build_modes == {"debug", "quick"}
            assert archive_types == {"thin", "regular"}

            for backup in compiler._library_backups:
                assert backup.backup_path.exists()
                assert backup.original_path.name in [
                    "libfastled.a",
                    "libfastled-thin.a",
                ]
                assert backup.build_mode in ["debug", "quick"]
                assert backup.archive_type in ["thin", "regular"]

    def test_backup_and_deletion(self) -> None:
        """Test that original files are deleted after backup."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=True),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # The backup system should backup BOTH library files since both exist
            regular_lib = self.build_root / "debug" / "libfastled.a"
            thin_lib = self.build_root / "debug" / "libfastled-thin.a"
            assert regular_lib.exists()
            assert thin_lib.exists()

            # Create backups
            compiler._backup_and_delete_libraries(["debug"], "test backup")

            # Verify both original files were deleted
            assert not regular_lib.exists()
            assert not thin_lib.exists()

            # Verify both backups were created
            assert len(compiler._library_backups) == 2

            # Check that we have both types backed up
            backup_types = {backup.archive_type for backup in compiler._library_backups}
            assert backup_types == {"thin", "regular"}

            # Verify all backup files exist
            for backup in compiler._library_backups:
                assert backup.backup_path.exists()
                assert backup.build_mode == "debug"

    def test_backup_restore(self) -> None:
        """Test that backups can be restored correctly."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # Get original content
            regular_lib = self.build_root / "debug" / "libfastled.a"
            original_content = regular_lib.read_text()

            # Create backups (this deletes originals)
            compiler._backup_and_delete_libraries(["debug"], "test backup")

            # Verify original was deleted
            assert not regular_lib.exists()

            # Restore backups
            compiler._restore_library_backups()

            # Verify file was restored with original content
            assert regular_lib.exists()
            assert regular_lib.read_text() == original_content

    def test_backup_cleanup(self) -> None:
        """Test that backup cleanup removes temporary files and directory."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # Create backups
            compiler._backup_and_delete_libraries(["debug"], "test backup")

            backup_dir = compiler._backup_temp_dir
            assert backup_dir is not None
            assert backup_dir.exists()
            assert len(list(backup_dir.iterdir())) > 0  # Has backup files

            # Clean up backups
            compiler._clear_library_backups()

            # Verify cleanup
            assert not backup_dir.exists()
            assert len(compiler._library_backups) == 0
            assert compiler._backup_temp_dir is None

    def test_no_backups_to_restore(self) -> None:
        """Test that restore handles the case with no backups gracefully."""
        compiler = CompilerImpl(volume_mapped_src=self.volume_src)

        # Try to restore with no backups - should not raise exception
        compiler._restore_library_backups()

        # Should remain empty
        assert len(compiler._library_backups) == 0

    def test_multiple_backup_cycles(self) -> None:
        """Test that multiple backup/restore cycles work correctly."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # First backup cycle
            compiler._backup_and_delete_libraries(["debug"], "first backup")
            first_backup_dir = compiler._backup_temp_dir
            assert first_backup_dir is not None
            assert first_backup_dir.exists()

            # Clear backups
            compiler._clear_library_backups()
            assert not first_backup_dir.exists()

            # Recreate the library file for second cycle
            regular_lib = self.build_root / "debug" / "libfastled.a"
            regular_lib.write_text("Second version content")

            # Second backup cycle
            compiler._backup_and_delete_libraries(["debug"], "second backup")
            second_backup_dir = compiler._backup_temp_dir
            assert second_backup_dir is not None
            assert second_backup_dir.exists()
            assert second_backup_dir != first_backup_dir  # Different temp dir

            # Verify second backup works
            compiler._restore_library_backups()
            assert regular_lib.exists()
            assert regular_lib.read_text() == "Second version content"

    def test_backup_with_missing_files(self) -> None:
        """Test backup behavior when some library files are missing."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # Remove one library file
            missing_lib = self.build_root / "quick" / "libfastled.a"
            missing_lib.unlink()

            # Create backups - should handle missing file gracefully
            compiler._backup_and_delete_libraries(
                ["debug", "quick", "release"], "test backup"
            )

            # Should have backups for debug and release (2 archive types each),
            # plus quick thin archive (since only regular was deleted)
            assert len(compiler._library_backups) == 5
            backed_up_modes = {
                backup.build_mode for backup in compiler._library_backups
            }
            assert backed_up_modes == {"debug", "quick", "release"}

            # Verify that quick only has thin archive (regular was deleted)
            quick_backups = [
                b for b in compiler._library_backups if b.build_mode == "quick"
            ]
            assert len(quick_backups) == 1
            assert quick_backups[0].archive_type == "thin"

    def test_legacy_method_compatibility(self) -> None:
        """Test that the legacy _check_and_delete_libraries method still works."""
        with (
            patch("fastled_wasm_compiler.compiler.BUILD_ROOT", self.build_root),
            patch("fastled_wasm_compiler.paths.can_use_thin_lto", return_value=False),
        ):

            compiler = CompilerImpl(volume_mapped_src=self.volume_src)

            # Use legacy method - should create backups
            compiler._check_and_delete_libraries(["debug"], "legacy test")

            # Verify backups were created (legacy method now uses backup mechanism)
            # Should backup both thin and regular archives for debug mode
            assert len(compiler._library_backups) == 2
            assert compiler._backup_temp_dir is not None
            assert compiler._backup_temp_dir.exists()

            # Verify both archive types were backed up
            archive_types = {
                backup.archive_type for backup in compiler._library_backups
            }
            assert archive_types == {"thin", "regular"}
