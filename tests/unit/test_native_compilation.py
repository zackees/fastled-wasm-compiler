"""
Unit tests for Native EMSDK Compilation

Tests the new native compilation system that uses locally installed EMSDK
instead of Docker containers. This validates the migration approach.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastled_wasm_compiler.compile_sketch_native import (
    NativeCompiler,
    compile_sketch_native,
)
from fastled_wasm_compiler.emsdk_manager import EmsdkManager


class TestNativeCompiler(unittest.TestCase):
    """Test NativeCompiler functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sketch_dir = self.temp_dir / "sketch"
        self.sketch_dir.mkdir()

        # Create mock EMSDK manager
        self.mock_emsdk_manager = Mock(spec=EmsdkManager)
        self.mock_emsdk_manager.emsdk_dir = self.temp_dir / "emsdk"
        self.mock_emsdk_manager.is_installed.return_value = True

        # Mock tool paths
        tools_dir = self.temp_dir / "tools"
        tools_dir.mkdir()
        self.mock_tool_paths = {
            "emcc": tools_dir / "emcc",
            "em++": tools_dir / "em++",
            "emar": tools_dir / "emar",
            "emranlib": tools_dir / "emranlib",
        }

        # Create mock tool files
        for tool_path in self.mock_tool_paths.values():
            tool_path.touch()

        self.mock_emsdk_manager.get_tool_paths.return_value = self.mock_tool_paths

        # Mock environment
        self.mock_env = {
            "PATH": "/mock/emsdk/bin:/usr/bin",
            "EMSDK": str(self.temp_dir / "emsdk"),
            "CCACHE_DIR": str(self.temp_dir / "ccache"),
        }
        self.mock_emsdk_manager.setup_environment.return_value = self.mock_env

    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_compiler_initialization(self, mock_get_emsdk_manager):
        """Test NativeCompiler initialization."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        compiler = NativeCompiler()

        self.assertIsNotNone(compiler.emsdk_manager)
        self.assertIsNotNone(compiler.base_flags)
        self.assertIsNotNone(compiler.debug_flags)
        self.assertIsNotNone(compiler.quick_flags)
        self.assertIsNotNone(compiler.release_flags)

    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_ensure_emsdk_already_installed(self, mock_get_emsdk_manager):
        """Test ensure_emsdk when EMSDK is already installed."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        compiler = NativeCompiler()
        compiler.ensure_emsdk()

        # Should not call install since is_installed returns True
        self.mock_emsdk_manager.install.assert_not_called()

    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_ensure_emsdk_needs_installation(self, mock_get_emsdk_manager):
        """Test ensure_emsdk when EMSDK needs installation."""
        self.mock_emsdk_manager.is_installed.return_value = False
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        compiler = NativeCompiler()
        compiler.ensure_emsdk()

        # Should call install since is_installed returns False
        self.mock_emsdk_manager.install.assert_called_once()

    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_get_compilation_env(self, mock_get_emsdk_manager):
        """Test getting compilation environment."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        compiler = NativeCompiler()
        env = compiler.get_compilation_env()

        self.assertEqual(env, self.mock_env)
        self.mock_emsdk_manager.setup_environment.assert_called_once()

    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_get_tool_paths(self, mock_get_emsdk_manager):
        """Test getting tool paths."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        compiler = NativeCompiler()
        tools = compiler.get_tool_paths()

        self.assertEqual(tools, self.mock_tool_paths)
        self.mock_emsdk_manager.get_tool_paths.assert_called_once()

    @patch("subprocess.run")
    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_compile_source_to_object_success(self, mock_get_emsdk_manager, mock_run):
        """Test successful source compilation."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        # Mock successful compilation
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Compilation successful"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Create test source file
        source_file = self.sketch_dir / "test.cpp"
        source_file.write_text("#include <stdio.h>\nint main() { return 0; }")

        # Create build directory
        build_dir = self.temp_dir / "build"

        compiler = NativeCompiler()

        # Mock the object file creation (since subprocess is mocked)
        expected_obj = build_dir / "test.o"
        build_dir.mkdir(parents=True, exist_ok=True)
        expected_obj.touch()  # Simulate object file creation

        obj_file = compiler.compile_source_to_object(source_file, "debug", build_dir)

        # Verify result
        self.assertEqual(obj_file, expected_obj)
        self.assertTrue(obj_file.exists())

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args

        # Check command structure
        cmd = call_args[0][0]
        self.assertIn(str(self.mock_tool_paths["em++"]), cmd)
        self.assertIn("-c", cmd)
        self.assertIn("-x", cmd)
        self.assertIn("c++", cmd)
        self.assertIn(str(source_file), cmd)
        self.assertIn(str(expected_obj), cmd)

        # Check environment was passed
        self.assertEqual(call_args[1]["env"], self.mock_env)

    @patch("subprocess.run")
    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_compile_source_to_object_failure(self, mock_get_emsdk_manager, mock_run):
        """Test source compilation failure."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        # Mock failed compilation
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Compilation error"
        mock_run.return_value = mock_result

        # Create test source file
        source_file = self.sketch_dir / "test.cpp"
        source_file.write_text("invalid C++ code")

        build_dir = self.temp_dir / "build"

        compiler = NativeCompiler()

        # Should raise RuntimeError on compilation failure
        with self.assertRaises(RuntimeError) as cm:
            compiler.compile_source_to_object(source_file, "debug", build_dir)

        self.assertIn("Failed to compile", str(cm.exception))
        self.assertIn("Compilation error", str(cm.exception))

    @patch("subprocess.run")
    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_link_objects_to_wasm_success(self, mock_get_emsdk_manager, mock_run):
        """Test successful WASM linking."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        # Mock successful linking
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Linking successful"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Create mock object files
        build_dir = self.temp_dir / "build"
        build_dir.mkdir()

        obj_files = [build_dir / "test1.o", build_dir / "test2.o"]
        for obj_file in obj_files:
            obj_file.touch()

        # Create output directory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        compiler = NativeCompiler()

        # Mock output file creation (since subprocess is mocked)
        expected_js = output_dir / "fastled.js"
        expected_wasm = output_dir / "fastled.wasm"
        expected_js.touch()
        expected_wasm.touch()

        js_file = compiler.link_objects_to_wasm(obj_files, "debug", output_dir)

        # Verify result
        self.assertEqual(js_file, expected_js)
        self.assertTrue(expected_js.exists())
        self.assertTrue(expected_wasm.exists())

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args

        # Check command structure
        cmd = call_args[0][0]
        self.assertIn(str(self.mock_tool_paths["em++"]), cmd)
        self.assertIn("-o", cmd)
        self.assertIn(str(expected_js), cmd)

        # Check object files are included
        for obj_file in obj_files:
            self.assertIn(str(obj_file), cmd)

    @patch("subprocess.run")
    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_link_objects_to_wasm_failure(self, mock_get_emsdk_manager, mock_run):
        """Test WASM linking failure."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        # Mock failed linking
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Linking error"
        mock_run.return_value = mock_result

        # Create mock object files
        build_dir = self.temp_dir / "build"
        build_dir.mkdir()
        obj_files = [build_dir / "test.o"]
        obj_files[0].touch()

        output_dir = self.temp_dir / "output"

        compiler = NativeCompiler()

        # Should raise RuntimeError on linking failure
        with self.assertRaises(RuntimeError) as cm:
            compiler.link_objects_to_wasm(obj_files, "debug", output_dir)

        self.assertIn("Failed to link", str(cm.exception))
        self.assertIn("Linking error", str(cm.exception))

    def test_build_mode_flag_selection(self):
        """Test that correct flags are selected for different build modes."""
        with patch(
            "fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager"
        ) as mock_get_emsdk_manager:
            mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

            compiler = NativeCompiler()

            # Test debug flags
            flags = compiler.base_flags.copy()
            flags.extend(compiler.debug_flags)
            self.assertIn("-g3", flags)
            self.assertIn("-O0", flags)
            self.assertIn("-fsanitize=address", flags)

            # Test quick flags
            quick_flags = compiler.base_flags.copy()
            quick_flags.extend(compiler.quick_flags)
            self.assertIn("-flto=thin", quick_flags)
            self.assertIn("-O0", quick_flags)
            self.assertIn("-sASSERTIONS=0", quick_flags)

            # Test release flags
            release_flags = compiler.base_flags.copy()
            release_flags.extend(compiler.release_flags)
            self.assertIn("-Oz", release_flags)
            self.assertIn("-DNDEBUG", release_flags)

    @patch("subprocess.run")
    @patch("fastled_wasm_compiler.compile_sketch_native.get_emsdk_manager")
    def test_compile_sketch_full_workflow(self, mock_get_emsdk_manager, mock_run):
        """Test complete sketch compilation workflow."""
        mock_get_emsdk_manager.return_value = self.mock_emsdk_manager

        # Mock successful compilation and linking
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Create test sketch files
        sketch_files = [
            self.sketch_dir / "main.cpp",
            self.sketch_dir / "helper.cpp",
            self.sketch_dir / "sketch.ino",
        ]

        for i, sketch_file in enumerate(sketch_files):
            sketch_file.write_text(f"// Test file {i}\nint test{i}() {{ return {i}; }}")

        compiler = NativeCompiler()

        # Mock file creation for all subprocess calls
        def mock_file_creation(*args, **kwargs):
            cmd = args[0]
            if "-c" in cmd:  # Compilation call
                # Find output object file
                try:
                    out_idx = cmd.index("-o") + 1
                    obj_path = Path(cmd[out_idx])
                    obj_path.parent.mkdir(parents=True, exist_ok=True)
                    obj_path.touch()
                except (ValueError, IndexError):
                    pass
            else:  # Linking call
                # Find output JS file
                try:
                    out_idx = cmd.index("-o") + 1
                    js_path = Path(cmd[out_idx])
                    wasm_path = js_path.with_suffix(".wasm")
                    js_path.parent.mkdir(parents=True, exist_ok=True)
                    js_path.touch()
                    wasm_path.touch()
                except (ValueError, IndexError):
                    pass
            return mock_result

        mock_run.side_effect = mock_file_creation

        # Compile sketch
        js_file = compiler.compile_sketch(self.sketch_dir, "debug")

        # Verify result
        self.assertTrue(js_file.exists())
        self.assertTrue(js_file.with_suffix(".wasm").exists())

        # Verify subprocess was called for compilation and linking
        self.assertGreaterEqual(mock_run.call_count, 4)  # 3 compilations + 1 linking


class TestNativeCompilationConvenience(unittest.TestCase):
    """Test convenience functions for native compilation."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sketch_dir = self.temp_dir / "sketch"
        self.sketch_dir.mkdir()

    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile_sketch_native.NativeCompiler")
    def test_compile_sketch_native_function(self, mock_compiler_class):
        """Test compile_sketch_native convenience function."""
        # Mock compiler instance
        mock_compiler = Mock()
        mock_js_file = self.temp_dir / "output.js"
        mock_js_file.touch()
        mock_compiler.compile_sketch.return_value = mock_js_file
        mock_compiler_class.return_value = mock_compiler

        # Call convenience function
        result = compile_sketch_native(
            sketch_dir=self.sketch_dir,
            build_mode="quick",
            output_dir=self.temp_dir / "output",
            emsdk_install_dir=self.temp_dir / "emsdk",
        )

        # Verify compiler was created with correct parameters
        mock_compiler_class.assert_called_once_with(self.temp_dir / "emsdk")

        # Verify compile_sketch was called with correct parameters
        mock_compiler.compile_sketch.assert_called_once_with(
            self.sketch_dir, "quick", self.temp_dir / "output"
        )

        self.assertEqual(result, mock_js_file)


class TestNativeCompilationIntegration(unittest.TestCase):
    """Integration tests for native compilation.

    These tests require actual EMSDK installation and are more expensive.
    They are only run when explicitly enabled.
    """

    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sketch_dir = self.temp_dir / "sketch"
        self.sketch_dir.mkdir()

        # Skip if integration tests not enabled
        if not os.environ.get("RUN_INTEGRATION_TESTS"):
            self.skipTest("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")

    def tearDown(self):
        """Clean up integration test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_native_compilation(self):
        """Test complete native compilation with real EMSDK."""
        # Create a simple test sketch
        sketch_file = self.sketch_dir / "test.cpp"
        sketch_file.write_text(
            """
#include <emscripten.h>
#include <stdio.h>

extern "C" {
    EMSCRIPTEN_KEEPALIVE
    int test_function() {
        printf("Hello from native compilation!\\n");
        return 42;
    }
}
"""
        )

        # Compile using native compiler
        js_file = compile_sketch_native(
            sketch_dir=self.sketch_dir,
            build_mode="quick",
            emsdk_install_dir=self.temp_dir / "emsdk",
        )

        # Verify output files exist
        self.assertTrue(js_file.exists())
        self.assertTrue(js_file.with_suffix(".wasm").exists())

        # Verify JS file contains expected content
        js_content = js_file.read_text()
        self.assertIn("Module", js_content)
        self.assertIn("fastled", js_content)  # Export name

        print(f"✅ Native compilation test successful: {js_file}")


if __name__ == "__main__":
    unittest.main()
