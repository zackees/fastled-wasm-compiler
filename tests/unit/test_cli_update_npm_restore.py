"""Unit tests for npm dependency restoration in cli_update_from_master."""

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.cli_update_from_master import main


class TestNpmRestore(unittest.TestCase):
    """Tests that npm install runs after sync when node_modules is missing."""

    @patch("fastled_wasm_compiler.cli_update_from_master._download")
    @patch("fastled_wasm_compiler.cli_update_from_master.sync_fastled")
    @patch("fastled_wasm_compiler.cli_update_from_master.shutil.which")
    @patch("fastled_wasm_compiler.cli_update_from_master.subprocess.run")
    def test_npm_install_called_when_node_modules_missing(
        self, mock_run: Any, mock_which: Any, mock_sync: Any, mock_download: Any
    ) -> None:
        """After sync, npm install should run if compiler dir exists but node_modules is gone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Set up the fake FastLED source that _download would produce
            fake_src = tmp_path / "fake_src"
            fake_src.mkdir(parents=True)

            # Set up the destination (simulating _FASTLED_SRC)
            fake_dst = tmp_path / "dst"
            fake_dst.mkdir(parents=True)

            # Create the compiler directory but NOT node_modules
            compiler_dir = fake_dst / "platforms" / "wasm" / "compiler"
            compiler_dir.mkdir(parents=True)

            # Mock sync_fastled to return a result with changes
            mock_sync_result = MagicMock()
            mock_sync_result.__bool__ = lambda self: True
            mock_sync.return_value = mock_sync_result

            # Mock which to return npm path
            mock_which.return_value = "/usr/bin/npm"

            # Mock subprocess.run for npm install
            mock_npm_result = MagicMock()
            mock_npm_result.returncode = 0
            mock_run.return_value = mock_npm_result

            # We need to patch the _FASTLED_SRC to our temp directory
            # and mock the download + zip extraction
            with patch(
                "fastled_wasm_compiler.cli_update_from_master._FASTLED_SRC", fake_dst
            ):
                # Mock the zipfile extraction to create expected structure
                with patch("zipfile.ZipFile") as mock_zip_class:
                    mock_zip = MagicMock()
                    mock_zip_class.return_value.__enter__ = lambda s: mock_zip

                    # Create the expected FastLED-master/src/FastLED.h structure
                    def fake_extractall(path: str) -> None:
                        master_dir = Path(path) / "FastLED-master" / "src"
                        master_dir.mkdir(parents=True, exist_ok=True)
                        (master_dir / "FastLED.h").write_text("// header")

                    mock_zip.extractall = fake_extractall
                    mock_zip_class.return_value.__exit__ = lambda s, *a: None

                    result = main()

            self.assertEqual(result, 0)
            # Verify npm install was called with correct cwd
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            self.assertEqual(call_args[0][0], ["/usr/bin/npm", "install"])
            self.assertEqual(call_args[1]["cwd"], compiler_dir)
            self.assertTrue(call_args[1]["check"])

    @patch("fastled_wasm_compiler.cli_update_from_master._download")
    @patch("fastled_wasm_compiler.cli_update_from_master.sync_fastled")
    @patch("fastled_wasm_compiler.cli_update_from_master.shutil.which")
    @patch("fastled_wasm_compiler.cli_update_from_master.subprocess.run")
    def test_npm_install_skipped_when_node_modules_exists(
        self, mock_run: Any, mock_which: Any, mock_sync: Any, mock_download: Any
    ) -> None:
        """If node_modules exists after sync, npm install should NOT run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            fake_dst = tmp_path / "dst"
            fake_dst.mkdir(parents=True)

            # Create compiler dir WITH node_modules
            compiler_dir = fake_dst / "platforms" / "wasm" / "compiler"
            compiler_dir.mkdir(parents=True)
            (compiler_dir / "node_modules").mkdir()

            mock_sync_result = MagicMock()
            mock_sync_result.__bool__ = lambda self: True
            mock_sync.return_value = mock_sync_result

            with patch(
                "fastled_wasm_compiler.cli_update_from_master._FASTLED_SRC", fake_dst
            ):
                with patch("zipfile.ZipFile") as mock_zip_class:
                    mock_zip = MagicMock()
                    mock_zip_class.return_value.__enter__ = lambda s: mock_zip

                    def fake_extractall(path: str) -> None:
                        master_dir = Path(path) / "FastLED-master" / "src"
                        master_dir.mkdir(parents=True, exist_ok=True)
                        (master_dir / "FastLED.h").write_text("// header")

                    mock_zip.extractall = fake_extractall
                    mock_zip_class.return_value.__exit__ = lambda s, *a: None

                    result = main()

            self.assertEqual(result, 0)
            # npm install should NOT have been called
            mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
