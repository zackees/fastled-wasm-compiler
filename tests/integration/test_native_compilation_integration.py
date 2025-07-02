"""
Integration tests for Native EMSDK Compilation

These tests require actual EMSDK installation and are expensive.
They should only be run when explicitly needed.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastled_wasm_compiler.compile_sketch_native import (
    NativeCompilerImpl,
    compile_sketch_native,
)
from fastled_wasm_compiler.emsdk_manager import EmsdkManager


class TestNativeCompilerIntegration(unittest.TestCase):
    """Integration tests for NativeCompiler that require EMSDK installation."""

    @classmethod
    def setUpClass(cls):
        """Set up shared cache for all integration tests."""
        # Use a persistent cache directory to speed up multiple test runs
        cls.shared_cache_dir = Path.cwd() / ".cache" / "test-emsdk-binaries"
        cls.shared_cache_dir.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        """Set up integration test environment."""
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

        # Set up EMSDK manager with shared cache
        self.emsdk_dir = self.temp_dir / "emsdk"
        self.emsdk_manager = EmsdkManager(
            install_dir=self.emsdk_dir, cache_dir=self.shared_cache_dir
        )

        # Skip if integration tests not enabled
        if not os.environ.get("RUN_INTEGRATION_TESTS"):
            self.skipTest("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")

    def tearDown(self):
        """Clean up integration test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Note: We don't clean up shared_cache_dir to preserve downloads

    def test_native_compilation_smoke_test(self):
        """Test basic native compilation functionality."""
        # Create compiler
        compiler = NativeCompilerImpl(self.emsdk_dir)

        # Compile the sketch
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        try:
            result = compiler.compile_sketch(
                sketch_dir=self.sketch_dir, build_mode="debug", output_dir=output_dir
            )

            # Check that compilation succeeded
            self.assertTrue(result.exists())

            # Check that output files were created
            output_files = list(output_dir.glob("*.js"))
            self.assertGreater(len(output_files), 0, "No JavaScript output files found")

            wasm_files = list(output_dir.glob("*.wasm"))
            self.assertGreater(len(wasm_files), 0, "No WASM output files found")

        except Exception as e:
            # If compilation fails, provide helpful error information
            self.fail(f"Native compilation failed: {e}")

    def test_compile_sketch_native_function(self):
        """Test the compile_sketch_native convenience function."""
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        try:
            result = compile_sketch_native(
                sketch_dir=self.sketch_dir,
                build_mode="quick",
                output_dir=output_dir,
                emsdk_install_dir=self.emsdk_dir,
            )

            # Check that compilation succeeded
            self.assertTrue(result.exists())

            # Check output files exist
            self.assertTrue(
                any(output_dir.glob("*.js")), "No JavaScript files generated"
            )
            self.assertTrue(any(output_dir.glob("*.wasm")), "No WASM files generated")

        except Exception as e:
            self.fail(f"Native compilation function failed: {e}")

    def test_different_build_modes(self):
        """Test compilation with different build modes."""
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        build_modes = ["debug", "quick", "release"]

        for mode in build_modes:
            with self.subTest(mode=mode):
                mode_output_dir = output_dir / mode
                mode_output_dir.mkdir()

                try:
                    result = compile_sketch_native(
                        sketch_dir=self.sketch_dir,
                        build_mode=mode,
                        output_dir=mode_output_dir,
                        emsdk_install_dir=self.emsdk_dir,
                    )

                    # Check that compilation succeeded
                    self.assertTrue(result.exists())

                    # Check output files exist
                    self.assertTrue(
                        any(mode_output_dir.glob("*.js")),
                        f"No JavaScript files generated for {mode} mode",
                    )
                    self.assertTrue(
                        any(mode_output_dir.glob("*.wasm")),
                        f"No WASM files generated for {mode} mode",
                    )

                except Exception as e:
                    self.fail(f"Native compilation failed for {mode} mode: {e}")


if __name__ == "__main__":
    unittest.main()
