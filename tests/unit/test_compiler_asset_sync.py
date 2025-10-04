"""Unit tests for compiler asset sync functionality and rebuild decisions."""

import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import Mock, patch

import pytest

from fastled_wasm_compiler.compiler import CompilerImpl
from fastled_wasm_compiler.sync import SyncResult


class TestCompilerAssetSync:
    """Test suite for compiler asset sync and rebuild decision logic."""

    @pytest.fixture
    def temp_dirs(self) -> Generator[Dict[str, Path], None, None]:
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source and destination directories
            src_dir = temp_path / "src"
            dst_dir = temp_path / "dst"
            src_dir.mkdir(parents=True)
            dst_dir.mkdir(parents=True)

            # Create basic FastLED structure
            (src_dir / "FastLED.h").write_text("#pragma once")

            # Create platforms/wasm/compiler structure for assets
            assets_dir = src_dir / "platforms" / "wasm" / "compiler"
            assets_dir.mkdir(parents=True)

            yield {
                "temp": temp_path,
                "src": src_dir,
                "dst": dst_dir,
                "assets": assets_dir,
            }

    @pytest.fixture
    def mock_compiler(self, temp_dirs: Dict[str, Path]) -> Generator[Any, None, None]:
        """Create a mock compiler instance."""
        build_root = temp_dirs["temp"] / "build"

        # Create fake library files to pass existence checks
        for mode in ["debug", "quick", "release"]:
            lib_dir = build_root / mode
            lib_dir.mkdir(parents=True, exist_ok=True)
            lib_file = lib_dir / "libfastled.a"
            lib_file.write_text("fake library")

        with patch("fastled_wasm_compiler.compiler.BUILD_ROOT", build_root):
            with patch("fastled_wasm_compiler.compiler.FASTLED_SRC", temp_dirs["dst"]):
                # Mock get_expected_archive_path where it's actually imported
                def get_archive_path(mode: str) -> Path:
                    return build_root / mode.lower() / "libfastled.a"

                with patch(
                    "fastled_wasm_compiler.paths.get_expected_archive_path",
                    get_archive_path,
                ):
                    compiler = CompilerImpl(volume_mapped_src=temp_dirs["src"])

                    # Mock the library checking to avoid filesystem dependencies
                    compiler._check_missing_libraries = Mock(return_value=[])
                    compiler._check_and_delete_libraries = Mock()
                    compiler._clear_library_backups = Mock()
                    compiler._restore_library_backups = Mock()

                    yield compiler

    def create_sync_result(
        self,
        all_files: Optional[List[Path]] = None,
        library_files: Optional[List[Path]] = None,
        asset_files: Optional[List[Path]] = None,
    ) -> SyncResult:
        """Helper to create a SyncResult object."""
        return SyncResult(
            all_changed_files=all_files or [],
            library_affecting_files=library_files or [],
            asset_only_files=asset_files or [],
        )

    def test_cpp_file_triggers_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that C++ file changes trigger library rebuild."""
        # Create a C++ file change
        cpp_file = temp_dirs["src"] / "test.cpp"
        cpp_file.write_text("// C++ source")

        # Mock the sync to return C++ file as library-affecting
        changed_file = temp_dirs["dst"] / "test.cpp"
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[changed_file], asset_files=[]
        )

        actual_sync_result = self.create_sync_result(
            all_files=[changed_file], library_files=[changed_file], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            # First call is dry run, second is actual
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                mock_compile.return_value = Mock(
                    return_code=0, duration=1.0, stdout="Success"
                )

                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was triggered
                mock_compile.assert_called_once()

                # Verify the result indicates library rebuild
                assert result.requires_library_rebuild()
                assert len(result.library_affecting_files) == 1
                assert len(result.asset_only_files) == 0

    def test_header_file_triggers_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that header file changes trigger library rebuild."""
        # Create a header file change
        header_file = temp_dirs["src"] / "test.h"
        header_file.write_text("#pragma once")

        # Mock the sync to return header file as library-affecting
        changed_file = temp_dirs["dst"] / "test.h"
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[changed_file], asset_files=[]
        )

        actual_sync_result = self.create_sync_result(
            all_files=[changed_file], library_files=[changed_file], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                mock_compile.return_value = Mock(
                    return_code=0, duration=1.0, stdout="Success"
                )

                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was triggered
                mock_compile.assert_called_once()
                assert result.requires_library_rebuild()

    def test_html_file_skips_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that HTML file changes do NOT trigger library rebuild."""
        # Create an HTML file change
        html_file = temp_dirs["assets"] / "index.html"
        html_file.write_text("<html><body>Updated</body></html>")

        # Mock the sync to return HTML file as asset-only
        changed_file = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.html"
        )
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        # Second sync returns empty (due to dry run side effect)
        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was NOT triggered
                mock_compile.assert_not_called()

                # Verify the result indicates NO library rebuild
                assert not result.requires_library_rebuild()
                assert len(result.library_affecting_files) == 0
                assert len(result.asset_only_files) == 1

                # Verify we used the dry run result (our fix!)
                assert len(result.files_changed) == 1

    def test_js_file_skips_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that JS file changes do NOT trigger library rebuild."""
        # Create a JS file change
        js_file = temp_dirs["assets"] / "index.js"
        js_file.write_text("console.log('updated');")

        # Mock the sync to return JS file as asset-only
        changed_file = temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.js"
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was NOT triggered
                mock_compile.assert_not_called()
                assert not result.requires_library_rebuild()
                assert len(result.asset_only_files) == 1

    def test_css_file_skips_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that CSS file changes do NOT trigger library rebuild."""
        # Create a CSS file change
        css_file = temp_dirs["assets"] / "index.css"
        css_file.write_text("body { margin: 0; }")

        # Mock the sync to return CSS file as asset-only
        changed_file = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.css"
        )
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was NOT triggered
                mock_compile.assert_not_called()
                assert not result.requires_library_rebuild()
                assert len(result.asset_only_files) == 1

    def test_mixed_changes_trigger_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that mixed changes (C++ and HTML) trigger library rebuild."""
        # Create both C++ and HTML file changes
        cpp_file = temp_dirs["src"] / "test.cpp"
        cpp_file.write_text("// C++ source")
        html_file = temp_dirs["assets"] / "index.html"
        html_file.write_text("<html><body>Updated</body></html>")

        # Mock the sync to return both files
        cpp_changed = temp_dirs["dst"] / "test.cpp"
        html_changed = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.html"
        )

        dry_run_result = self.create_sync_result(
            all_files=[cpp_changed, html_changed],
            library_files=[cpp_changed],
            asset_files=[html_changed],
        )

        actual_sync_result = self.create_sync_result(
            all_files=[cpp_changed, html_changed],
            library_files=[cpp_changed],
            asset_files=[html_changed],
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                mock_compile.return_value = Mock(
                    return_code=0, duration=1.0, stdout="Success"
                )

                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation WAS triggered (due to C++ file)
                mock_compile.assert_called_once()
                assert result.requires_library_rebuild()
                assert len(result.library_affecting_files) == 1
                assert len(result.asset_only_files) == 1

    def test_asset_only_with_missing_libraries(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that asset-only changes with missing libraries still trigger rebuild."""
        # Mock missing libraries
        mock_compiler._check_missing_libraries = Mock(return_value=["debug", "quick"])

        # Create an HTML file change
        html_file = temp_dirs["assets"] / "index.html"
        html_file.write_text("<html><body>Updated</body></html>")

        # Mock the sync to return HTML file as asset-only
        changed_file = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.html"
        )
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        actual_sync_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                mock_compile.return_value = Mock(
                    return_code=0, duration=1.0, stdout="Success"
                )

                # Create the libraries after compilation to pass verification
                def create_libraries_side_effect(*args: Any, **kwargs: Any) -> Mock:
                    # Create the missing libraries to pass verification
                    for mode in ["debug", "quick"]:
                        lib_file = temp_dirs["temp"] / "build" / mode / "libfastled.a"
                        lib_file.parent.mkdir(parents=True, exist_ok=True)
                        lib_file.write_text("compiled library")
                    return Mock(return_code=0, duration=1.0, stdout="Success")

                mock_compile.side_effect = create_libraries_side_effect

                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # When libraries are missing (force_recompile=True) AND only asset files change,
                # the current logic still triggers rebuild because force_recompile takes precedence
                # So library compilation SHOULD be triggered
                mock_compile.assert_called_once()

                # The result still shows asset files correctly classified
                assert len(result.asset_only_files) == 1

    def test_no_changes_skips_everything(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that no file changes skip both sync and rebuild."""
        # Mock the sync to return no changes
        dry_run_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.return_value = dry_run_result

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was NOT triggered
                mock_compile.assert_not_called()

                # Verify only one sync call (dry run)
                mock_sync.assert_called_once_with(
                    src=temp_dirs["src"], dst=temp_dirs["dst"], dryrun=True
                )

                # Verify the result indicates no changes
                assert len(result.files_changed) == 0
                assert not result.requires_library_rebuild()
                assert result.error is None

    def test_multiple_asset_files_skip_rebuild(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test that multiple asset-only file changes skip library rebuild."""
        # Create multiple asset file changes
        html_file = temp_dirs["assets"] / "index.html"
        html_file.write_text("<html><body>Updated</body></html>")
        js_file = temp_dirs["assets"] / "index.js"
        js_file.write_text("console.log('updated');")
        css_file = temp_dirs["assets"] / "index.css"
        css_file.write_text("body { margin: 0; }")

        # Mock the sync to return multiple asset files
        html_changed = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.html"
        )
        js_changed = temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.js"
        css_changed = temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.css"

        dry_run_result = self.create_sync_result(
            all_files=[html_changed, js_changed, css_changed],
            library_files=[],
            asset_files=[html_changed, js_changed, css_changed],
        )

        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify library compilation was NOT triggered
                mock_compile.assert_not_called()
                assert not result.requires_library_rebuild()
                assert len(result.asset_only_files) == 3
                assert len(result.files_changed) == 3

    def test_dry_run_fallback_mechanism(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test the dry run result fallback when actual sync returns empty."""
        # This specifically tests our fix for the double-sync issue

        # Create an HTML file change
        html_file = temp_dirs["assets"] / "index.html"
        html_file.write_text("<html><body>Updated</body></html>")

        # Mock the sync - dry run shows changes, actual shows none
        changed_file = (
            temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.html"
        )
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        # This is the key case: actual sync returns empty
        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]  # Empty!
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # Verify the fallback mechanism worked
                assert len(result.files_changed) == 1  # From dry run result
                assert len(result.asset_only_files) == 1  # From dry run result
                assert result.files_changed[0] == changed_file

                # Verify no library rebuild
                mock_compile.assert_not_called()

    def test_rsync_web_assets_direct(self, temp_dirs: Dict[str, Path]) -> None:
        """Test the direct rsync functionality for web assets."""
        from fastled_wasm_compiler.sync import _sync_web_assets_with_rsync

        # Create web asset files in source
        assets_src = temp_dirs["assets"]
        (assets_src / "index.html").write_text("<html><body>Test</body></html>")
        (assets_src / "index.js").write_text("console.log('test');")
        (assets_src / "index.css").write_text("body { margin: 0; }")
        (assets_src / "README.txt").write_text("This should be ignored")

        # Create destination directory
        assets_dst = temp_dirs["temp"] / "dst_assets"

        # Test rsync sync
        result = _sync_web_assets_with_rsync(assets_src, assets_dst, dryrun=False)

        # Verify files were synced
        assert (assets_dst / "index.html").exists()
        assert (assets_dst / "index.js").exists()
        assert (assets_dst / "index.css").exists()
        # README.txt should be excluded by rsync filters
        assert not (assets_dst / "README.txt").exists()

        # Verify result classification
        assert len(result.asset_only_files) == 3  # html, js, css
        assert len(result.library_affecting_files) == 0
        assert len(result.all_changed_files) == 3

    def test_rsync_web_assets_with_deletion(self, temp_dirs: Dict[str, Path]) -> None:
        """Test that rsync properly deletes removed files."""
        from fastled_wasm_compiler.sync import _sync_web_assets_with_rsync

        # Create initial files
        assets_src = temp_dirs["assets"]
        assets_dst = temp_dirs["temp"] / "dst_assets"
        assets_dst.mkdir(parents=True)

        # Create files in both src and dst
        (assets_src / "keep.html").write_text("<html>Keep</html>")
        (assets_src / "keep.js").write_text("console.log('keep');")
        (assets_dst / "keep.html").write_text("<html>Keep</html>")
        (assets_dst / "keep.js").write_text("console.log('keep');")
        (assets_dst / "remove.html").write_text("<html>Remove</html>")
        (assets_dst / "remove.css").write_text("body { color: red; }")

        # First sync - should remove files not in source
        result = _sync_web_assets_with_rsync(assets_src, assets_dst, dryrun=False)

        # Verify files were properly managed
        assert (assets_dst / "keep.html").exists()
        assert (assets_dst / "keep.js").exists()
        assert not (assets_dst / "remove.html").exists()  # Should be deleted
        assert not (assets_dst / "remove.css").exists()  # Should be deleted

        # Verify result
        assert len(result.asset_only_files) == 2  # Only the files that exist

    def test_missing_libraries_with_empty_sync_result(
        self, mock_compiler: Any, temp_dirs: Dict[str, Path]
    ) -> None:
        """Test exact bug scenario: missing libraries + dry run shows assets + actual sync empty.

        This is the specific bug from the error report where:
        1. Libraries are missing (force_recompile=True)
        2. Dry run shows asset changes (26 web files)
        3. Actual sync returns empty (because assets were already synced)
        4. Bug: code returned early without rebuilding libraries
        5. Fix: check force_recompile before early return
        """
        # Mock missing libraries
        mock_compiler._check_missing_libraries = Mock(return_value=["quick"])

        # Dry run shows asset changes
        changed_file = temp_dirs["dst"] / "platforms" / "wasm" / "compiler" / "index.js"
        dry_run_result = self.create_sync_result(
            all_files=[changed_file], library_files=[], asset_files=[changed_file]
        )

        # Actual sync returns EMPTY (key part of the bug)
        actual_sync_result = self.create_sync_result(
            all_files=[], library_files=[], asset_files=[]
        )

        with patch("fastled_wasm_compiler.compiler.sync_fastled") as mock_sync:
            mock_sync.side_effect = [dry_run_result, actual_sync_result]

            with patch(
                "fastled_wasm_compiler.compiler.compile_all_libs"
            ) as mock_compile:
                # Create libraries after compilation to pass verification
                def create_libraries_side_effect(*args: Any, **kwargs: Any) -> Mock:
                    lib_file = temp_dirs["temp"] / "build" / "quick" / "libfastled.a"
                    lib_file.parent.mkdir(parents=True, exist_ok=True)
                    lib_file.write_text("compiled library")
                    return Mock(return_code=0, duration=1.0, stdout="Success")

                mock_compile.side_effect = create_libraries_side_effect

                result = mock_compiler.update_src(src_to_merge_from=temp_dirs["src"])

                # THE FIX: Even though actual sync returned empty,
                # libraries were missing, so compilation MUST be triggered
                mock_compile.assert_called_once()

                # Should not have an error
                assert result.error is None
