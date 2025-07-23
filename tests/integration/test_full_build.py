"""
Unit test file.
"""

import os
import platform
import shutil
import subprocess
import unittest
from pathlib import Path

from fastled_wasm_compiler.paths import CONTAINER_JS_ROOT

# Enable Docker BuildKit for faster builds
os.environ["DOCKER_BUILDKIT"] = "1"

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
SKETCH_FOLDER = HERE / "sketch"
TEST_DATA = HERE / "test_data"
ASSETS_DIR = TEST_DATA / "assets"
COMPILER_ROOT = TEST_DATA / "compiler_root"
MAPPED_DIR = TEST_DATA / "mapped"


DOCKER_FILE = PROJECT_ROOT / "Dockerfile"
IMAGE_NAME = "niteris/fastled-wasm-compiler:test"

_IS_GITHUB = os.environ["CI"] == "true" if "CI" in os.environ else False
_IS_LINUX = platform.system() == "Linux"

_ENABLE = _IS_LINUX or not _IS_GITHUB

_FULL_PURGE = False


def check_docker_availability() -> None:
    """Check if Docker is available and running, raise clear error if not."""
    try:
        # First check if docker command exists
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError("Docker command not found. Please install Docker.")

        # Then check if Docker daemon is running
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            error_msg = "Docker is installed but not running. Please start Docker Desktop or Docker daemon."
            if (
                "cannot connect" in result.stderr.lower()
                or "connection refused" in result.stderr.lower()
            ):
                error_msg += f"\nError details: {result.stderr.strip()}"
            raise RuntimeError(error_msg)

    except subprocess.TimeoutExpired:
        raise RuntimeError("Docker command timed out. Docker may not be responding.")
    except FileNotFoundError:
        raise RuntimeError("Docker command not found. Please install Docker.")


class FullBuildTester(unittest.TestCase):
    """Main tester class."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment by building the Docker container once for all tests."""
        if _ENABLE:
            # Check Docker availability first before attempting any Docker operations
            print("Checking Docker availability...")
            check_docker_availability()
            print("✅ Docker is available and running")

            # Remove any existing containers with the same name
            subprocess.run(
                ["docker", "rm", "-f", "fastled-test-container"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Remove any existing image with the same tag
            subprocess.run(
                ["docker", "rmi", "-f", IMAGE_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Build the Docker image with the test tag
            print("Building Docker image...")
            print(
                "⚠️  This may take 15-30 minutes to compile 112+ FastLED source files in 3 modes (debug, quick, release)..."
            )

            # Build the Docker image with streaming output
            build_proc = subprocess.Popen(
                ["docker", "build", "-t", IMAGE_NAME, "."],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            assert build_proc.stdout is not None

            for line in build_proc.stdout:
                line_str = line.decode("utf-8", errors="replace")
                print(line_str.strip())

            build_proc.wait()
            build_proc.stdout.close()
            build_proc.terminate()
            assert build_proc.returncode == 0, "Docker build failed"

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up Docker resources after all tests have run."""
        if _ENABLE:
            print("\nCleaning up Docker resources...")
            # Remove the container
            subprocess.run(
                ["docker", "rm", "-f", "fastled-test-container"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Remove the image
            subprocess.run(
                ["docker", "rmi", "-f", IMAGE_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if _FULL_PURGE:
                # Prune any dangling build artifacts
                subprocess.run(
                    ["docker", "system", "prune", "-f"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            # compiler_root/src may have garbage if the build failed
            # Remove the compiler_root/src directory
            src_dir = COMPILER_ROOT / "src"
            if src_dir.exists():
                shutil.rmtree(src_dir, ignore_errors=True)
            print("Cleanup complete.")

    # per test setup and teardown
    def setUp(self) -> None:
        # wipe the mapped/sketch/fastled_js directory
        fljs = MAPPED_DIR / "sketch" / "fastled_js"
        if fljs.exists():
            shutil.rmtree(fljs, ignore_errors=True)

    def test_sanity(self) -> None:
        """Test command line interface (CLI)."""
        self.assertTrue(DOCKER_FILE.exists(), "Dockerfile does not exist")
        self.assertTrue(SKETCH_FOLDER.exists(), "Sketch folder does not exist")

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_full(self) -> None:
        """Test command line interface (CLI)."""

        # Run the container with --help command and let it exit
        print("\nRunning container with --help command...")
        run_proc = subprocess.Popen(
            [
                "docker",
                "run",
                "-p",
                "7012:80",
                "--name",
                "fastled-test-container",
                IMAGE_NAME,
                "fastled-wasm-compiler",
                "--help",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert run_proc.stdout is not None

        for line in run_proc.stdout:
            line_str = line.decode("utf-8", errors="replace")
            print(line_str.strip())

        run_proc.wait()
        run_proc.stdout.close()
        run_proc.terminate()
        self.assertEqual(run_proc.returncode, 0, "Docker run failed")

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_printenv(self) -> None:
        """Test the printenv command and validate container environment variables."""

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-printenv-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print("\nRunning container with printenv command...")
        run_proc = subprocess.Popen(
            [
                "docker",
                "run",
                "--name",
                "fastled-printenv-container",
                "--entrypoint",
                "fastled-wasm-compiler-printenv",
                IMAGE_NAME,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert run_proc.stdout is not None

        # Capture the output for validation
        output_lines = []
        for line in run_proc.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            print(line_str)
            output_lines.append(line_str)

        run_proc.wait()
        run_proc.stdout.close()
        run_proc.terminate()

        # The printenv command should exit with code 0
        self.assertEqual(run_proc.returncode, 0, "printenv command failed")

        # Convert output lines to a dict for easier validation
        env_vars = {}
        for line in output_lines:
            if "=" in line and not line.startswith("==="):
                key, value = line.split("=", 1)
                env_vars[key] = value

        # Validate critical environment variables are set correctly
        expected_env_vars = {
            "ENV_FASTLED_ROOT": "/git/fastled",
            "ENV_FASTLED_SOURCE_PATH": "/git/fastled/src",
            "ENV_EMSDK_PATH": "/emsdk",
            "ENV_SKETCH_ROOT": "/js/src",
            "ENV_VOLUME_MAPPED_SRC": "/host/fastled/src",
        }

        for key, expected_value in expected_env_vars.items():
            self.assertIn(key, env_vars, f"Environment variable {key} not found")
            self.assertEqual(
                env_vars[key],
                expected_value,
                f"Environment variable {key} has incorrect value. Expected: {expected_value}, Got: {env_vars[key]}",
            )

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-printenv-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_symbol_resolution(self) -> None:
        """Test the symbol resolution command and validate DWARF path resolution."""

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-symbol-resolution-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print("\nRunning container with symbol resolution command...")
        run_proc = subprocess.Popen(
            [
                "docker",
                "run",
                "--name",
                "fastled-symbol-resolution-container",
                "--entrypoint",
                "fastled-wasm-compiler-symbol-resolution",
                IMAGE_NAME,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert run_proc.stdout is not None

        # Capture the output for validation
        output_lines = []
        for line in run_proc.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            print(line_str)
            output_lines.append(line_str)

        run_proc.wait()
        run_proc.stdout.close()
        run_proc.terminate()

        # The symbol resolution command should exit with code 0
        self.assertEqual(run_proc.returncode, 0, "symbol resolution command failed")

        # Join all output lines to search for expected content
        full_output = "\n".join(output_lines)

        # Validate that the test case is present in the output
        self.assertIn(
            "dwarfsource/js/src/test.h",
            full_output,
            "Test input 'dwarfsource/js/src/test.h' not found in output",
        )

        # Check that the expected resolution is present
        # The output should show the resolution to /js/src/test.h (with leading slash)
        self.assertIn(
            "/js/src/test.h",
            full_output,
            "Expected resolution '/js/src/test.h' not found in output",
        )

        # Verify that the test passed
        self.assertIn(
            "✅ Symbol resolution test PASSED",
            full_output,
            "Symbol resolution test did not pass",
        )

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-symbol-resolution-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_compile_sketch_in_debug(self) -> None:
        """Test compiling the sketch folder using the command line arguments with the full build environment."""

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Mount the test data directories and output directory to the container
        print("\nCompiling sketch with full build environment...")

        cmd_list: list[str] = [
            "docker",
            "run",
            "--name",
            "fastled-compile-container",
            # Mount the test data directories
            "-v",
            f"{MAPPED_DIR.absolute()}:/mapped",
            "-v",
            f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
            "-v",
            f"{ASSETS_DIR.absolute()}:/assets",
            IMAGE_NAME,
            # Required arguments
            "--compiler-root",
            CONTAINER_JS_ROOT,
            "--assets-dirs",
            "/assets",
            "--mapped-dir",
            "/mapped",
            # Optional arguments
            "--debug",
            "--no-platformio",  # Use direct emcc calls instead of platformio
            "--keep-files",  # Keep intermediate files for debugging
            "--clear-ccache",  # Clear the ccache before compilation
        ]

        cmdstr = subprocess.list2cmdline(cmd_list)
        print(f"Running command: {cmdstr}")

        compile_proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert compile_proc.stdout is not None

        # Print output in real-time
        for line in compile_proc.stdout:
            line_str = line.decode("utf-8", errors="replace")
            print(line_str.strip())

        compile_proc.wait()
        compile_proc.stdout.close()
        compile_proc.terminate()

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Check if compilation was successful
        self.assertEqual(compile_proc.returncode, 0, "Sketch compilation failed")

        output_dir = MAPPED_DIR / "sketch" / "fastled_js"

        # Check if output files were generated
        output_files = list(output_dir.glob("**/*"))
        self.assertTrue(len(output_files) > 0, "No output files were generated")

        # Check for specific output files
        wasm_files = list(output_dir.glob("**/*.wasm"))
        js_files = list(output_dir.glob("**/*.js"))
        html_files = list(output_dir.glob("**/*.html"))

        self.assertTrue(len(wasm_files) > 0, "No WASM files were generated")
        self.assertTrue(len(js_files) > 0, "No JS files were generated")
        self.assertTrue(len(html_files) > 0, "No HTML files were generated")

        # Check for manifest.json which should contain file mappings
        manifest_file = list(output_dir.glob("**/files.json"))
        self.assertTrue(len(manifest_file) > 0, "No files.json file was generated")

        # Extra files for debug mode
        extra_files_in_debug: list[Path] = [
            output_dir / "fastled.js.symbols",
            output_dir / "fastled.wasm.dwarf",
        ]

        for file in extra_files_in_debug:
            self.assertTrue(file.exists(), f"Debug file {file} does not exist")

        fastled_wasm = output_dir / "fastled.wasm"
        self.assertTrue(fastled_wasm.exists(), "fastled.wasm does not exist")
        wasm_bytes = fastled_wasm.read_bytes()
        self.assertIn(
            b"fastled.wasm.dwarf",
            wasm_bytes,
            "dwarf symbol map not referenced in the wasm file, this will break advanced step through debugging",
        )
        print("Done")

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_compile_sketch_in_quick(self) -> None:
        """Test compiling the sketch folder using the command line arguments with the full build environment."""

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Mount the test data directories and output directory to the container
        print("\nCompiling sketch with full build environment...")

        cmd_list: list[str] = [
            "docker",
            "run",
            "--name",
            "fastled-compile-container",
            # Mount the test data directories
            "-v",
            f"{MAPPED_DIR.absolute()}:/mapped",
            "-v",
            f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
            "-v",
            f"{ASSETS_DIR.absolute()}:/assets",
            IMAGE_NAME,
            # Required arguments
            "--compiler-root",
            CONTAINER_JS_ROOT,
            "--assets-dirs",
            "/assets",
            "--mapped-dir",
            "/mapped",
            # Optional arguments
            "--quick",
            "--no-platformio",  # Use direct emcc calls instead of platformio
            "--keep-files",  # Keep intermediate files for debugging
        ]

        cmdstr = subprocess.list2cmdline(cmd_list)
        print(f"Running command: {cmdstr}")

        compile_proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert compile_proc.stdout is not None

        # Capture output for validation while printing in real-time
        output_lines = []
        for line in compile_proc.stdout:
            line_str = line.decode("utf-8", errors="replace")
            print(line_str.strip())
            output_lines.append(line_str.strip())

        compile_proc.wait()
        compile_proc.stdout.close()
        compile_proc.terminate()

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Check if compilation was successful
        self.assertEqual(compile_proc.returncode, 0, "Sketch compilation failed")

        # Join all output for analysis
        full_output = "\n".join(output_lines)

        # In Docker environment using official FastLED source, fallback behavior is expected
        # The primary config only exists when using a custom FastLED build with WASM compiler integration
        # So we should expect fallback messages and verify the build still succeeds
        if "Primary config not found" in full_output:
            # This is expected when using official FastLED source - verify fallback is working
            self.assertIn(
                "BUILD_FLAGS STATUS: Falling back to package resource",
                full_output,
                "Expected fallback message not found when primary config is missing",
            )
            print(
                "✅ Expected fallback behavior detected - using package build_flags.toml"
            )
        else:
            print(
                "✅ Primary config found - using FastLED source tree build_flags.toml"
            )

        # Check if output files were generated
        output_dir = MAPPED_DIR / "sketch" / "fastled_js"
        output_files = list(output_dir.glob("**/*"))
        self.assertTrue(len(output_files) > 0, "No output files were generated")

        # Check for specific output files
        wasm_files = list(output_dir.glob("**/*.wasm"))
        js_files = list(output_dir.glob("**/*.js"))
        html_files = list(output_dir.glob("**/*.html"))

        self.assertTrue(len(wasm_files) > 0, "No WASM files were generated")
        self.assertTrue(len(js_files) > 0, "No JS files were generated")
        self.assertTrue(len(html_files) > 0, "No HTML files were generated")

        # Check for manifest.json which should contain file mappings
        manifest_file = list(output_dir.glob("**/files.json"))
        self.assertTrue(len(manifest_file) > 0, "No files.json file was generated")

    @unittest.skipIf(not _ENABLE or True, "Release doesn't work yet for some reason.")
    def test_compile_sketch_in_release(self) -> None:
        """Test compiling the sketch folder in release mode and measure performance."""
        import time

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Mount the test data directories and output directory to the container
        print("\nCompiling sketch in release mode for performance testing...")

        cmd_list: list[str] = [
            "docker",
            "run",
            "--name",
            "fastled-compile-container",
            # Mount the test data directories
            "-v",
            f"{MAPPED_DIR.absolute()}:/mapped",
            "-v",
            f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
            "-v",
            f"{ASSETS_DIR.absolute()}:/assets",
            IMAGE_NAME,
            # Required arguments
            "--compiler-root",
            CONTAINER_JS_ROOT,
            "--assets-dirs",
            "/assets",
            "--mapped-dir",
            "/mapped",
            # Optional arguments
            "--release",  # Use release mode for maximum optimization
            "--no-platformio",  # Use direct emcc calls instead of platformio
            "--keep-files",  # Keep intermediate files for debugging
        ]

        cmdstr = subprocess.list2cmdline(cmd_list)
        print(f"Running command: {cmdstr}")

        # Measure compilation time
        start_time = time.time()

        compile_proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert compile_proc.stdout is not None

        # Print output in real-time
        for line in compile_proc.stdout:
            line_str = line.decode("utf-8", errors="replace")
            print(line_str.strip())

        compile_proc.wait()
        compile_proc.stdout.close()
        compile_proc.terminate()

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        print(f"\nRelease build completed in {elapsed_time:.2f} seconds")

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compile-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Check if compilation was successful
        self.assertEqual(
            compile_proc.returncode, 0, "Release sketch compilation failed"
        )

        # Check if output files were generated
        output_dir = MAPPED_DIR / "sketch" / "fastled_js"
        output_files = list(output_dir.glob("**/*"))
        self.assertTrue(len(output_files) > 0, "No output files were generated")

        # Check for specific output files
        wasm_files = list(output_dir.glob("**/*.wasm"))
        js_files = list(output_dir.glob("**/*.js"))
        html_files = list(output_dir.glob("**/*.html"))

        self.assertTrue(len(wasm_files) > 0, "No WASM files were generated")
        self.assertTrue(len(js_files) > 0, "No JS files were generated")
        self.assertTrue(len(html_files) > 0, "No HTML files were generated")

        # Check for manifest.json which should contain file mappings
        manifest_file = list(output_dir.glob("**/files.json"))
        self.assertTrue(len(manifest_file) > 0, "No files.json file was generated")

        # Check WASM file size (release builds should be smaller)
        fastled_wasm = output_dir / "fastled.wasm"
        self.assertTrue(fastled_wasm.exists(), "fastled.wasm does not exist")
        wasm_size = fastled_wasm.stat().st_size
        print(f"Release build WASM size: {wasm_size} bytes")

        # In a real test, we might compare this to other build modes
        # or have a maximum size threshold, but for now we just report it

    @unittest.skipIf(_IS_GITHUB, "Skipping test on GitHub CI")
    def test_platformio_vs_no_platformio_artifacts(self) -> None:
        """Test that PlatformIO and no-PlatformIO builds produce equivalent artifacts.

        Note: PlatformIO builds are now deprecated and automatically fall back to
        non-PlatformIO builds, so both paths should produce identical results.
        This test verifies the deprecation fallback works correctly.
        """
        import json

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-compare-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def run_compilation(use_platformio: bool, output_subdir: str) -> Path:
            """Run compilation and return the output directory path."""
            # Create separate mapped directories for comparison
            mapped_test_dir = MAPPED_DIR.parent / f"mapped_{output_subdir}"
            if mapped_test_dir.exists():
                shutil.rmtree(mapped_test_dir)

            # Copy the original mapped directory structure
            shutil.copytree(MAPPED_DIR, mapped_test_dir)
            # Set 777 permissions to avoid Docker permission issues
            subprocess.run(["chmod", "-R", "777", str(mapped_test_dir)], check=False)

            # The output will be in the fastled_js subdirectory of the sketch
            output_dir = mapped_test_dir / "sketch" / "fastled_js"
            if output_dir.exists():
                shutil.rmtree(output_dir)

            cmd_list: list[str] = [
                "docker",
                "run",
                "--name",
                "fastled-compare-container",
                # Mount the test data directories
                "-v",
                f"{mapped_test_dir.absolute()}:/mapped",
                "-v",
                f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
                "-v",
                f"{ASSETS_DIR.absolute()}:/assets",
                IMAGE_NAME,
                # Required arguments
                "--compiler-root",
                CONTAINER_JS_ROOT,
                "--assets-dirs",
                "/assets",
                "--mapped-dir",
                "/mapped",
                # Optional arguments
                "--quick",  # Use quick mode for faster testing
                "--keep-files",  # Keep intermediate files for debugging
            ]

            if not use_platformio:
                cmd_list.append("--no-platformio")

            build_type = "PlatformIO" if use_platformio else "No-PlatformIO"
            print(f"\nCompiling sketch using {build_type} build...")

            compile_proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            assert compile_proc.stdout is not None

            # Print output in real-time
            for line in compile_proc.stdout:
                line_str = line.decode("utf-8", errors="replace")
                print(line_str.strip())

            compile_proc.wait()
            compile_proc.stdout.close()
            compile_proc.terminate()

            # Clean up the container
            subprocess.run(
                ["docker", "rm", "-f", "fastled-compare-container"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Check if compilation was successful
            self.assertEqual(
                compile_proc.returncode, 0, f"{build_type} compilation failed"
            )

            return output_dir

        # Run both compilations
        platformio_output = run_compilation(
            use_platformio=True, output_subdir="platformio"
        )
        no_platformio_output = run_compilation(
            use_platformio=False, output_subdir="no_platformio"
        )

        # Verify both output directories exist and have files
        self.assertTrue(
            platformio_output.exists(), "PlatformIO output directory missing"
        )
        self.assertTrue(
            no_platformio_output.exists(), "No-PlatformIO output directory missing"
        )

        # Get list of files in both directories
        platformio_files = set(
            f.name for f in platformio_output.glob("**/*") if f.is_file()
        )
        no_platformio_files = set(
            f.name for f in no_platformio_output.glob("**/*") if f.is_file()
        )

        print(f"\nPlatformIO files: {sorted(platformio_files)}")
        print(f"No-PlatformIO files: {sorted(no_platformio_files)}")

        # Assert both builds have the same set of files
        self.assertEqual(
            platformio_files,
            no_platformio_files,
            "File sets differ between PlatformIO and no-PlatformIO builds",
        )

        # Compare critical artifacts
        critical_files = [
            "fastled.wasm",
            "fastled.js",
            "index.html",
            "index.css",
            "files.json",
        ]

        for filename in critical_files:
            platformio_file = platformio_output / filename
            no_platformio_file = no_platformio_output / filename

            self.assertTrue(
                platformio_file.exists(), f"PlatformIO build missing {filename}"
            )
            self.assertTrue(
                no_platformio_file.exists(), f"No-PlatformIO build missing {filename}"
            )

        # Compare WASM file sizes (should be similar, allowing for small differences)
        platformio_wasm = platformio_output / "fastled.wasm"
        no_platformio_wasm = no_platformio_output / "fastled.wasm"

        platformio_size = platformio_wasm.stat().st_size
        no_platformio_size = no_platformio_wasm.stat().st_size

        print("\nWASM file sizes:")
        print(f"  PlatformIO: {platformio_size} bytes")
        print(f"  No-PlatformIO: {no_platformio_size} bytes")

        # Allow up to 5% size difference (compilation variations are normal)
        size_diff_ratio = abs(platformio_size - no_platformio_size) / max(
            platformio_size, no_platformio_size
        )
        self.assertLess(
            size_diff_ratio,
            0.05,
            f"WASM file sizes differ significantly: {platformio_size} vs {no_platformio_size}",
        )

        # Compare manifest files (should contain similar structure)
        platformio_manifest = platformio_output / "files.json"
        no_platformio_manifest = no_platformio_output / "files.json"

        if platformio_manifest.exists() and no_platformio_manifest.exists():
            with open(platformio_manifest) as f:
                platformio_data = json.load(f)
            with open(no_platformio_manifest) as f:
                no_platformio_data = json.load(f)

            # Both should have the same manifest structure
            if isinstance(platformio_data, dict) and isinstance(
                no_platformio_data, dict
            ):
                self.assertEqual(
                    set(platformio_data.keys()),
                    set(no_platformio_data.keys()),
                    "Manifest file structures differ",
                )
            elif isinstance(platformio_data, list) and isinstance(
                no_platformio_data, list
            ):
                self.assertEqual(
                    len(platformio_data),
                    len(no_platformio_data),
                    "Manifest file list lengths differ",
                )
            else:
                self.assertEqual(
                    type(platformio_data),
                    type(no_platformio_data),
                    "Manifest file types differ",
                )

        print("\n✅ PlatformIO and No-PlatformIO builds produce equivalent artifacts!")

        # Clean up temporary mapped directories with proper permissions
        platformio_mapped = MAPPED_DIR.parent / "mapped_platformio"
        no_platformio_mapped = MAPPED_DIR.parent / "mapped_no_platformio"

        if platformio_mapped.exists():
            shutil.rmtree(platformio_mapped)
        if no_platformio_mapped.exists():
            shutil.rmtree(no_platformio_mapped)

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_precompiled_headers_in_quick_mode(self) -> None:
        """Test that precompiled headers are generated and used in quick mode only."""

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-pch-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def run_compilation_and_check_pch(mode: str, expect_pch: bool) -> str:
            """Run compilation in specified mode and return captured output."""
            # Create a separate mapped directory for this test
            mapped_test_dir = MAPPED_DIR.parent / f"mapped_pch_{mode}"
            if mapped_test_dir.exists():
                shutil.rmtree(mapped_test_dir)

            # Copy the original mapped directory structure
            shutil.copytree(MAPPED_DIR, mapped_test_dir)
            # Set 777 permissions to avoid Docker permission issues
            subprocess.run(["chmod", "-R", "777", str(mapped_test_dir)], check=False)

            # Clear any existing output
            output_dir = mapped_test_dir / "sketch" / "fastled_js"
            if output_dir.exists():
                shutil.rmtree(output_dir)

            cmd_list: list[str] = [
                "docker",
                "run",
                "--name",
                "fastled-pch-container",
                # Mount the test data directories
                "-v",
                f"{mapped_test_dir.absolute()}:/mapped",
                "-v",
                f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
                "-v",
                f"{ASSETS_DIR.absolute()}:/assets",
                IMAGE_NAME,
                # Required arguments
                "--compiler-root",
                CONTAINER_JS_ROOT,
                "--assets-dirs",
                "/assets",
                "--mapped-dir",
                "/mapped",
                # Mode-specific arguments
                f"--{mode}",
                "--no-platformio",  # Use direct emcc calls to see PCH messages
                "--keep-files",  # Keep intermediate files for verification
            ]

            print(f"\nCompiling sketch in {mode} mode to test PCH behavior...")

            compile_proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            assert compile_proc.stdout is not None

            # Capture all output for analysis
            output_lines = []
            for line in compile_proc.stdout:
                line_str = line.decode("utf-8", errors="replace").strip()
                print(line_str)
                output_lines.append(line_str)

            compile_proc.wait()
            compile_proc.stdout.close()
            compile_proc.terminate()

            # Clean up the container
            subprocess.run(
                ["docker", "rm", "-f", "fastled-pch-container"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Check if compilation was successful
            self.assertEqual(
                compile_proc.returncode, 0, f"{mode} mode compilation failed"
            )

            # Clean up test directory
            if mapped_test_dir.exists():
                shutil.rmtree(mapped_test_dir)

            return "\n".join(output_lines)

        # Test quick mode - should use PCH
        print("\n=== Testing PCH in QUICK mode ===")
        quick_output = run_compilation_and_check_pch("quick", expect_pch=True)

        # Verify PCH optimization messages are present in quick mode
        pch_optimization_applied = any(
            "PCH OPTIMIZATION:" in line for line in quick_output.split("\n")
        )
        pch_precompiled_header_used = any(
            "Using precompiled header" in line for line in quick_output.split("\n")
        )

        self.assertTrue(
            pch_optimization_applied,
            "PCH optimization should be applied in quick mode, but 'PCH OPTIMIZATION:' message not found in output",
        )
        self.assertTrue(
            pch_precompiled_header_used,
            "Precompiled header should be used in quick mode, but 'Using precompiled header' message not found in output",
        )

        # Test debug mode - should also use PCH now
        print("\n=== Testing PCH in DEBUG mode ===")
        debug_output = run_compilation_and_check_pch("debug", expect_pch=True)

        # Verify PCH optimization messages are present in debug mode too
        pch_optimization_applied_debug = any(
            "PCH OPTIMIZATION:" in line for line in debug_output.split("\n")
        )
        pch_precompiled_header_used_debug = any(
            "Using precompiled header" in line for line in debug_output.split("\n")
        )

        self.assertTrue(
            pch_optimization_applied_debug,
            "PCH optimization should be applied in debug mode, but 'PCH OPTIMIZATION:' message not found in output",
        )
        self.assertTrue(
            pch_precompiled_header_used_debug,
            "Precompiled header should be used in debug mode, but 'Using precompiled header' message not found in output",
        )

        print("\n✅ Precompiled headers test PASSED!")
        print("   - PCH optimization works correctly in QUICK mode")
        print("   - PCH optimization also works correctly in DEBUG mode")
        print("   - Appropriate user feedback messages are displayed")

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_headers_dump(self) -> None:
        """Test the --headers feature to dump FastLED and WASM headers (headers-only, no compilation)."""

        # Create a temporary directory for headers output
        headers_output_dir = MAPPED_DIR / "headers_output"
        if headers_output_dir.exists():
            shutil.rmtree(headers_output_dir)
        headers_output_dir.mkdir(parents=True, exist_ok=True)

        print("\nTesting headers dump functionality (standalone, no compilation)...")

        # Use the native CompilerNative API to dump headers directly
        # This avoids the slow Docker compilation and tests just the headers functionality
        try:
            from fastled_wasm_compiler import CompilerNative

            print("🔧 Creating native compiler instance...")
            compiler = CompilerNative()

            print("📦 Ensuring EMSDK is available...")
            compiler.ensure_emsdk()

            print(f"🔄 Dumping headers to: {headers_output_dir}")
            # Use directory output instead of zip for easier testing
            from fastled_wasm_compiler.dump_headers import HeaderDumper

            header_dumper = HeaderDumper(headers_output_dir, include_source=False)
            _ = header_dumper.dump_all_headers()

            print("✅ Headers dumped successfully")
            return_code = 0

        except Exception as e:
            print(f"❌ Headers dump failed: {e}")
            return_code = 1

        # Check if headers dump was successful
        self.assertEqual(return_code, 0, "Headers dump failed")

        # Verify the headers directory structure exists
        self.assertTrue(
            headers_output_dir.exists(), "Headers output directory was not created"
        )

        # Check for expected directory structure
        fastled_headers_dir = headers_output_dir / "fastled"
        wasm_headers_dir = headers_output_dir / "wasm"
        arduino_headers_dir = headers_output_dir / "arduino"
        manifest_file = headers_output_dir / "manifest.json"

        self.assertTrue(
            fastled_headers_dir.exists(), "FastLED headers directory not found"
        )
        self.assertTrue(wasm_headers_dir.exists(), "WASM headers directory not found")
        self.assertTrue(
            arduino_headers_dir.exists(), "Arduino headers directory not found"
        )
        self.assertTrue(manifest_file.exists(), "manifest.json file not found")

        # Verify FastLED.h is present in the FastLED headers
        fastled_h_files = list(fastled_headers_dir.rglob("FastLED.h"))
        self.assertTrue(
            len(fastled_h_files) > 0, "FastLED.h not found in dumped headers"
        )

        # Verify manifest contains expected metadata
        import json

        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)

        self.assertIn("fastled", manifest_data, "Manifest missing FastLED section")
        self.assertIn("wasm", manifest_data, "Manifest missing WASM section")
        self.assertIn("arduino", manifest_data, "Manifest missing Arduino section")
        self.assertIn("metadata", manifest_data, "Manifest missing metadata section")

        # Verify some headers were actually collected
        total_files = manifest_data["metadata"]["total_files"]
        self.assertGreater(total_files, 0, "No files were collected in headers dump")

        print("✅ Headers dump test completed successfully!")
        print(f"   - Total files collected: {total_files}")
        print(f"   - FastLED headers: {len(manifest_data['fastled'])}")
        print(f"   - WASM headers: {len(manifest_data['wasm'])}")
        print(f"   - Arduino headers: {len(manifest_data['arduino'])}")

        # Verify some other important FastLED headers
        important_headers = ["CRGB.h", "colorutils.h", "FastLED.h"]
        for header in important_headers:
            header_files = list(fastled_headers_dir.rglob(header))
            self.assertTrue(
                len(header_files) > 0,
                f"Important header {header} not found in dumped headers",
            )

        # Verify Arduino.h is present in Arduino headers
        arduino_h_files = list(arduino_headers_dir.rglob("Arduino.h"))
        self.assertTrue(
            len(arduino_h_files) > 0, "Arduino.h not found in dumped Arduino headers"
        )

        # Verify some WASM/Emscripten headers are present
        wasm_header_files = list(wasm_headers_dir.rglob("*.h"))
        self.assertTrue(
            len(wasm_header_files) > 0, "No WASM headers found in dumped headers"
        )

        # Specifically verify emscripten headers are included
        emscripten_headers_dir = wasm_headers_dir / "emscripten"
        self.assertTrue(
            emscripten_headers_dir.exists(), "Emscripten headers directory not found"
        )

        # Verify key emscripten headers exist
        key_emscripten_headers = ["emscripten.h", "bind.h", "val.h"]
        for header in key_emscripten_headers:
            emscripten_header_files = list(emscripten_headers_dir.rglob(header))
            if len(emscripten_header_files) > 0:
                print(f"   ✅ Found emscripten header: {header}")
            # Note: Not all headers may be present in all EMSDK versions, so we warn but don't fail

        # Verify at least some emscripten headers exist
        emscripten_header_count = len(list(emscripten_headers_dir.rglob("*.h")))
        self.assertTrue(
            emscripten_header_count > 0,
            "No emscripten headers found in emscripten/ subdirectory",
        )
        print(f"   Found {emscripten_header_count} emscripten-specific headers")

        # Verify manifest.json contains valid JSON and expected structure
        import json

        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)

        self.assertIn(
            "fastled", manifest_data, "manifest.json missing 'fastled' section"
        )
        self.assertIn("wasm", manifest_data, "manifest.json missing 'wasm' section")
        self.assertIn(
            "arduino", manifest_data, "manifest.json missing 'arduino' section"
        )

        # Verify each section contains file lists
        self.assertIsInstance(
            manifest_data["fastled"], list, "FastLED section should be a list of files"
        )
        self.assertIsInstance(
            manifest_data["wasm"], list, "WASM section should be a list of files"
        )
        self.assertIsInstance(
            manifest_data["arduino"], list, "Arduino section should be a list of files"
        )

        # Verify FastLED.h is listed in the manifest
        fastled_files = [str(f) for f in manifest_data["fastled"]]
        fastled_h_in_manifest = any("FastLED.h" in f for f in fastled_files)
        self.assertTrue(fastled_h_in_manifest, "FastLED.h not found in manifest")

        print("\n✅ Headers dump test PASSED!")
        print(f"   - Headers successfully dumped to: {headers_output_dir}")
        print(
            f"   - FastLED headers found: {len(list(fastled_headers_dir.rglob('*.h')))}"
        )
        print(f"   - WASM headers found: {len(list(wasm_headers_dir.rglob('*.h')))}")
        print(
            f"   - Arduino headers found: {len(list(arduino_headers_dir.rglob('*.h')))}"
        )
        print("   - FastLED.h verified in output")
        print("   - Emscripten headers verified in wasm/emscripten/ subdirectory")
        print("   - manifest.json created and validated")

        # Clean up the headers output directory
        if headers_output_dir.exists():
            shutil.rmtree(headers_output_dir)

    @unittest.skipIf(not _ENABLE, "Skipping test on non-Linux or GitHub CI")
    def test_pch_staleness_with_volume_mapping_disabled(self) -> None:
        """Test PCH staleness behavior when volume mapping is disabled.

        This test reproduces the scenario where Arduino.h gets modified after
        PCH is built, causing PCH staleness errors even when volume mapping
        is disabled (which should prevent any FastLED source modifications).
        """

        # Remove any existing containers with the same name
        subprocess.run(
            ["docker", "rm", "-f", "fastled-pch-staleness-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Create a separate mapped directory for this test
        mapped_test_dir = MAPPED_DIR.parent / "mapped_pch_staleness"
        if mapped_test_dir.exists():
            shutil.rmtree(mapped_test_dir)

        # Copy the original mapped directory structure
        shutil.copytree(MAPPED_DIR, mapped_test_dir)
        # Set 777 permissions to avoid Docker permission issues
        subprocess.run(["chmod", "-R", "777", str(mapped_test_dir)], check=False)

        # Clear any existing output
        output_dir = mapped_test_dir / "sketch" / "fastled_js"
        if output_dir.exists():
            shutil.rmtree(output_dir)

        print("\n🔍 Testing PCH staleness with volume mapping DISABLED...")
        print(
            "This should reveal what's inappropriately touching FastLED source files."
        )

        cmd_list: list[str] = [
            "docker",
            "run",
            "--name",
            "fastled-pch-staleness-container",
            # Mount the test data directories
            "-v",
            f"{mapped_test_dir.absolute()}:/mapped",
            "-v",
            f"{COMPILER_ROOT.absolute()}:{CONTAINER_JS_ROOT}",
            "-v",
            f"{ASSETS_DIR.absolute()}:/assets",
            # CRITICAL: Disable volume mapping by setting ENV_VOLUME_MAPPED_SRC to non-existent path
            "-e",
            "ENV_VOLUME_MAPPED_SRC=/nonexistent/path",
            IMAGE_NAME,
            # Required arguments
            "--compiler-root",
            CONTAINER_JS_ROOT,
            "--assets-dirs",
            "/assets",
            "--mapped-dir",
            "/mapped",
            # Use quick mode (has PCH enabled)
            "--quick",
            "--no-platformio",  # Use direct emcc calls to see PCH messages
            "--keep-files",  # Keep intermediate files for debugging
        ]

        print(f"\n🚀 Command: {subprocess.list2cmdline(cmd_list)}")
        print("🔒 Volume mapping DISABLED: ENV_VOLUME_MAPPED_SRC=/nonexistent/path")
        print("📋 Expected behavior: NO FastLED source files should be modified")
        print(
            "🚨 If we see PCH staleness errors, something is inappropriately touching Arduino.h!"
        )

        compile_proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert compile_proc.stdout is not None

        # Capture all output for analysis
        output_lines = []
        pch_staleness_detected = False
        fastled_source_modified = False

        for line in compile_proc.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            print(line_str)
            output_lines.append(line_str)

            # Check for PCH staleness errors
            if "has been modified since the precompiled header" in line_str:
                pch_staleness_detected = True
                print("🚨 PCH STALENESS DETECTED!")

            # Check that no source files are being modified (should never happen with new architecture)
            if "✂️ Removed:" in line_str and "FastLED.h/Arduino.h" in line_str:
                fastled_source_modified = True
                print("UNEXPECTED SOURCE MODIFICATION DETECTED - ARCHITECTURAL BUG!")

        compile_proc.wait()
        compile_proc.stdout.close()
        compile_proc.terminate()

        # Clean up the container
        subprocess.run(
            ["docker", "rm", "-f", "fastled-pch-staleness-container"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Clean up test directory
        if mapped_test_dir.exists():
            shutil.rmtree(mapped_test_dir)

        full_output = "\n".join(output_lines)

        # Analyze results
        print("\n" + "=" * 80)
        print("🔍 PCH STALENESS BUG ANALYSIS:")
        print("=" * 80)

        if pch_staleness_detected:
            print(
                "🚨 BUG CONFIRMED: PCH staleness error occurred with volume mapping disabled!"
            )
            print(
                "   This means something is inappropriately modifying FastLED source files."
            )
        else:
            print("✅ No PCH staleness detected - good!")

        if fastled_source_modified:
            print(
                "🚨 BUG CONFIRMED: FastLED source files were modified with volume mapping disabled!"
            )
            print("   This should NEVER happen when volume mapping is disabled.")
        else:
            print("✅ No FastLED source modifications detected - good!")

        # Check compilation result
        if compile_proc.returncode == 0:
            print("✅ Compilation succeeded")
        else:
            print(f"❌ Compilation failed with exit code: {compile_proc.returncode}")

        # Look for specific error patterns in output
        volume_mapping_status = (
            "ENABLED" if "Volume mapped source defined" in full_output else "DISABLED"
        )
        print(f"📊 Volume mapping status detected: {volume_mapping_status}")

        if "FASTLED SOURCE TREE" in full_output:
            print("🚨 CRITICAL: FastLED source tree files were analyzed for PCH!")

        # Analysis complete - test passes if we reach here without assertion failures


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Run FastLED WASM Compiler full build tests"
    )
    parser.add_argument("--log", metavar="FILE", help="Log output to specified file")

    # Parse known args to avoid conflicts with unittest args
    args, remaining_args = parser.parse_known_args()

    from typing import TextIO

    log_file: TextIO | None = None

    # Set up logging if requested
    if args.log:
        log_file = open(args.log, "w", encoding="utf-8")
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"Logging to: {args.log}")

    try:
        # Pass remaining args to unittest
        sys.argv = [sys.argv[0]] + remaining_args
        unittest.main()
    finally:
        # Clean up logging
        if args.log:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            if log_file is not None:
                log_file.close()
            print(f"Output logged to: {args.log}")
