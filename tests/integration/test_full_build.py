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


class FullBuildTester(unittest.TestCase):
    """Main tester class."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment by building the Docker container once for all tests."""
        if _ENABLE:
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


if __name__ == "__main__":
    unittest.main()
