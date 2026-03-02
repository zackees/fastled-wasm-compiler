"""Unit tests for vite_build.py."""

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.vite_build import ensure_vite_built


class TestEnsureViteBuilt(unittest.TestCase):
    """Tests for ensure_vite_built()."""

    def test_returns_immediately_when_dist_is_complete(self) -> None:
        """If dist/ has index.html and index.js, no rebuild happens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            dist_dir = compiler_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / "index.html").write_text("<html></html>")
            (dist_dir / "index.js").write_text("// js")

            result = ensure_vite_built(compiler_dir)
            self.assertEqual(result, dist_dir)

    def test_incomplete_dist_triggers_rebuild(self) -> None:
        """If dist/ exists but is missing essential files, rebuild is triggered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            dist_dir = compiler_dir / "dist"
            dist_dir.mkdir()
            # Only create index.html, missing index.js
            (dist_dir / "index.html").write_text("<html></html>")
            # Also create node_modules so npm install is skipped
            (compiler_dir / "node_modules").mkdir()

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("shutil.which", return_value="/usr/bin/npx"):
                with patch("subprocess.run", return_value=mock_result) as mock_run:
                    # Create the missing file so the post-build check passes
                    def side_effect(*args: Any, **kwargs: Any) -> Any:
                        (dist_dir / "index.js").write_text("// built")
                        return mock_result

                    mock_run.side_effect = side_effect
                    result = ensure_vite_built(compiler_dir)

                    self.assertEqual(result, dist_dir)
                    mock_run.assert_called_once()
                    # Verify vite build was called
                    call_args = mock_run.call_args[0][0]
                    self.assertIn("vite", call_args)
                    self.assertIn("build", call_args)

    def test_missing_dist_triggers_rebuild(self) -> None:
        """If dist/ doesn't exist at all, rebuild is triggered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            dist_dir = compiler_dir / "dist"
            # Also create node_modules so npm install is skipped
            (compiler_dir / "node_modules").mkdir()

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("shutil.which", return_value="/usr/bin/npx"):
                with patch("subprocess.run", return_value=mock_result) as mock_run:

                    def side_effect(*args: Any, **kwargs: Any) -> Any:
                        dist_dir.mkdir(exist_ok=True)
                        (dist_dir / "index.html").write_text("<html></html>")
                        (dist_dir / "index.js").write_text("// built")
                        return mock_result

                    mock_run.side_effect = side_effect
                    result = ensure_vite_built(compiler_dir)

                    self.assertEqual(result, dist_dir)
                    mock_run.assert_called_once()

    def test_npm_install_runs_when_node_modules_missing(self) -> None:
        """If node_modules/ is missing, npm install runs before vite build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            dist_dir = compiler_dir / "dist"
            # No node_modules directory

            mock_result = MagicMock()
            mock_result.returncode = 0

            def which_side_effect(cmd: str) -> str | None:
                if cmd in ("npx", "npm"):
                    return f"/usr/bin/{cmd}"
                return None

            with patch("shutil.which", side_effect=which_side_effect):
                with patch("subprocess.run", return_value=mock_result) as mock_run:
                    call_count = [0]

                    def side_effect(*args: Any, **kwargs: Any) -> Any:
                        call_count[0] += 1
                        if call_count[0] == 1:
                            # npm install call - create node_modules
                            (compiler_dir / "node_modules").mkdir(exist_ok=True)
                        elif call_count[0] == 2:
                            # vite build call - create dist
                            dist_dir.mkdir(exist_ok=True)
                            (dist_dir / "index.html").write_text("<html></html>")
                            (dist_dir / "index.js").write_text("// built")
                        return mock_result

                    mock_run.side_effect = side_effect
                    result = ensure_vite_built(compiler_dir)

                    self.assertEqual(result, dist_dir)
                    self.assertEqual(mock_run.call_count, 2)
                    # First call: npm install
                    first_call_args = mock_run.call_args_list[0][0][0]
                    self.assertIn("install", first_call_args)
                    # Second call: vite build
                    second_call_args = mock_run.call_args_list[1][0][0]
                    self.assertIn("vite", second_call_args)
                    self.assertIn("build", second_call_args)

    def test_raises_when_npx_not_found(self) -> None:
        """If npx is not on PATH, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            # No dist directory

            with patch("shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    ensure_vite_built(compiler_dir)
                self.assertIn("npx not found", str(ctx.exception))

    def test_raises_when_npm_not_found_and_node_modules_missing(self) -> None:
        """If npm is missing and node_modules doesn't exist, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            # No dist, no node_modules

            def which_side_effect(cmd: str) -> str | None:
                if cmd == "npx":
                    return "/usr/bin/npx"
                return None  # npm not found

            with patch("shutil.which", side_effect=which_side_effect):
                with self.assertRaises(RuntimeError) as ctx:
                    ensure_vite_built(compiler_dir)
                self.assertIn("npm not found", str(ctx.exception))

    def test_raises_when_vite_build_fails(self) -> None:
        """If vite build returns non-zero exit code, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            (compiler_dir / "node_modules").mkdir()

            mock_result = MagicMock()
            mock_result.returncode = 127
            mock_result.stderr = "sh: 1: vite: not found"

            with patch("shutil.which", return_value="/usr/bin/npx"):
                with patch("subprocess.run", return_value=mock_result):
                    with self.assertRaises(RuntimeError) as ctx:
                        ensure_vite_built(compiler_dir)
                    self.assertIn("Vite build failed", str(ctx.exception))
                    self.assertIn("exit code 127", str(ctx.exception))

    def test_raises_when_npm_install_fails(self) -> None:
        """If npm install returns non-zero exit code, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            # No node_modules

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "npm ERR! some error"

            def which_side_effect(cmd: str) -> str | None:
                if cmd in ("npx", "npm"):
                    return f"/usr/bin/{cmd}"
                return None

            with patch("shutil.which", side_effect=which_side_effect):
                with patch("subprocess.run", return_value=mock_result):
                    with self.assertRaises(RuntimeError) as ctx:
                        ensure_vite_built(compiler_dir)
                    self.assertIn("npm install failed", str(ctx.exception))

    def test_raises_when_dist_not_created_after_build(self) -> None:
        """If vite build succeeds but dist/ is not created, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler_dir = Path(tmpdir)
            (compiler_dir / "node_modules").mkdir()

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("shutil.which", return_value="/usr/bin/npx"):
                with patch("subprocess.run", return_value=mock_result):
                    with self.assertRaises(RuntimeError) as ctx:
                        ensure_vite_built(compiler_dir)
                    self.assertIn("dist/ directory was not created", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
