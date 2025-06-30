"""
Unit tests for Native EMSDK Compilation

Tests the new native compilation system that uses locally installed EMSDK
instead of Docker containers. This validates the migration approach.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from fastled_wasm_compiler.compile_sketch_native import (
    NativeCompiler,
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

    def test_native_compiler_creation(self):
        """Test creating a native compiler instance."""
        compiler = NativeCompiler(self.emsdk_dir)

        self.assertIsInstance(compiler, NativeCompiler)
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

    def test_compiler_initialization(self):
        """Test compiler initialization."""
        compiler = NativeCompiler(self.emsdk_dir)

        self.assertIsInstance(compiler, NativeCompiler)
        self.assertEqual(compiler.emsdk_manager.install_dir, self.emsdk_dir)

    def test_compiler_requires_emsdk_manager(self):
        """Test that compiler can be initialized with or without emsdk_install_dir."""
        # Should work with None (uses default)
        compiler = NativeCompiler(None)
        self.assertIsInstance(compiler, NativeCompiler)

        # Should work with custom path
        compiler = NativeCompiler(self.emsdk_dir)
        self.assertIsInstance(compiler, NativeCompiler)


if __name__ == "__main__":
    unittest.main()
