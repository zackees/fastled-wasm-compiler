"""
Unit tests for Native EMSDK Compilation

Tests the new native compilation system that uses locally installed EMSDK
instead of Docker containers. This validates the migration approach.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastled_wasm_compiler.compile_sketch_native import (
    NativeCompilerImpl,
)
from fastled_wasm_compiler.emsdk_manager import EmsdkManager


class TestNativeCompiler(unittest.TestCase):
    """Test NativeCompiler functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sketch_dir = self.temp_dir / "sketch"
        self.sketch_dir.mkdir()

        # Create a simple test sketch
        sketch_content = """
#include "FastLED.h"

#define NUM_LEDS 10
#define DATA_PIN 3

CRGB leds[NUM_LEDS];

void setup() {
    FastLED.addLeds<WS2812, DATA_PIN, GRB>(leds, NUM_LEDS);
}

void loop() {
    fill_rainbow(leds, NUM_LEDS, 0, 255/NUM_LEDS);
    FastLED.show();
    delay(100);
}
"""
        (self.sketch_dir / "sketch.ino").write_text(sketch_content)

        # Set up EMSDK manager
        self.emsdk_dir = self.temp_dir / "emsdk"
        self.emsdk_manager = EmsdkManager(install_dir=self.emsdk_dir)

    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile_sketch_native.ensure_fastled_installed")
    def test_native_compiler_creation(self, mock_fastled):
        """Test creating a native compiler instance."""
        # Mock FastLED installation
        mock_fastled_src = self.temp_dir / "fastled" / "src"
        mock_fastled_src.mkdir(parents=True)
        (mock_fastled_src / "FastLED.h").write_text("// Mock FastLED header")
        mock_fastled.return_value = mock_fastled_src

        compiler = NativeCompilerImpl(self.emsdk_dir)

        self.assertIsInstance(compiler, NativeCompilerImpl)
        self.assertEqual(compiler.emsdk_manager.install_dir, self.emsdk_dir)


class TestNativeCompilerUnit(unittest.TestCase):
    """Unit tests for NativeCompiler that don't require EMSDK installation."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.emsdk_dir = self.temp_dir / "emsdk"
        self.emsdk_manager = EmsdkManager(install_dir=self.emsdk_dir)

    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile_sketch_native.ensure_fastled_installed")
    def test_compiler_initialization(self, mock_fastled):
        """Test compiler initialization."""
        # Mock FastLED installation
        mock_fastled_src = self.temp_dir / "fastled" / "src"
        mock_fastled_src.mkdir(parents=True)
        (mock_fastled_src / "FastLED.h").write_text("// Mock FastLED header")
        mock_fastled.return_value = mock_fastled_src

        compiler = NativeCompilerImpl(self.emsdk_dir)

        self.assertIsInstance(compiler, NativeCompilerImpl)
        self.assertEqual(compiler.emsdk_manager.install_dir, self.emsdk_dir)

    @patch("fastled_wasm_compiler.compile_sketch_native.ensure_fastled_installed")
    def test_compiler_requires_emsdk_manager(self, mock_fastled):
        """Test that compiler can be initialized with or without emsdk_install_dir."""
        # Mock FastLED installation
        mock_fastled_src = self.temp_dir / "fastled" / "src"
        mock_fastled_src.mkdir(parents=True)
        (mock_fastled_src / "FastLED.h").write_text("// Mock FastLED header")
        mock_fastled.return_value = mock_fastled_src

        # Should work with None (uses default)
        compiler = NativeCompilerImpl(None)
        self.assertIsInstance(compiler, NativeCompilerImpl)

        # Should work with custom path
        compiler = NativeCompilerImpl(self.emsdk_dir)
        self.assertIsInstance(compiler, NativeCompilerImpl)


if __name__ == "__main__":
    unittest.main()
