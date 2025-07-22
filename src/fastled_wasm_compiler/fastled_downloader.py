"""
FastLED Downloader for Native Compilation

This module handles downloading and setting up the FastLED library
for native compilation environments.
"""

import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import httpx

from fastled_wasm_compiler.paths import FASTLED_ROOT


class FastLEDDownloader:
    """Downloads and sets up FastLED for native compilation."""

    FASTLED_VERSION = "master"
    FASTLED_URL = (
        f"https://github.com/FastLED/FastLED/archive/refs/heads/{FASTLED_VERSION}.zip"
    )

    def __init__(self, install_dir: Path | None = None) -> None:
        """Initialize FastLED downloader.

        Args:
            install_dir: Directory to install FastLED to. Defaults to FASTLED_ROOT from paths.py
        """
        self.install_dir = install_dir or FASTLED_ROOT
        self.fastled_src = self.install_dir / "src"

    def is_installed(self) -> bool:
        """Check if FastLED is already installed."""
        fastled_header = self.fastled_src / "FastLED.h"
        return fastled_header.exists()

    def _safe_rmtree(self, path: Path, max_retries: int = 3) -> None:
        """Safely remove a directory tree, handling Windows file locking issues."""
        for attempt in range(max_retries):
            try:
                if path.exists():
                    # On Windows, make files writable before deletion
                    if os.name == "nt":
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                file_path = Path(root) / file
                                try:
                                    file_path.chmod(0o777)
                                except (OSError, PermissionError):
                                    pass  # Ignore permission errors on individual files

                    shutil.rmtree(path)
                    break
            except (OSError, PermissionError) as e:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed to remove {path}: {e}")
                    print("Retrying after 1 second...")
                    time.sleep(1)
                else:
                    print(
                        f"Warning: Could not remove {path} after {max_retries} attempts: {e}"
                    )
                    print("This may cause issues with subsequent installations.")

    def download_and_extract(self) -> None:
        """Download and extract FastLED from GitHub."""
        print(f"Downloading FastLED {self.FASTLED_VERSION}...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_file = temp_path / "fastled.zip"

            # Download FastLED archive
            print(f"Downloading from {self.FASTLED_URL}")
            with httpx.stream(
                "GET", self.FASTLED_URL, follow_redirects=True, timeout=300
            ) as response:
                response.raise_for_status()
                with open(zip_file, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            # Extract archive
            print(f"Extracting to {self.install_dir}")
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # Move extracted directory to final location
            extracted_dir = temp_path / f"FastLED-{self.FASTLED_VERSION}"
            if extracted_dir.exists():
                # Remove existing installation if it exists
                if self.install_dir.exists():
                    self._safe_rmtree(self.install_dir)

                # Create parent directory
                self.install_dir.parent.mkdir(parents=True, exist_ok=True)

                # Move to final location
                shutil.move(str(extracted_dir), str(self.install_dir))
            else:
                raise RuntimeError(
                    f"Expected extracted directory not found: {extracted_dir}"
                )

    def cleanup_platforms(self) -> None:
        """Remove unnecessary platform directories and files to match Docker setup."""
        platforms_dir = self.fastled_src / "platforms"
        if not platforms_dir.exists():
            return

        print("Cleaning up platforms directory...")

        # Keep only wasm, stub, and shared directories
        for item in platforms_dir.iterdir():
            if item.is_dir():
                if item.name not in ["wasm", "stub", "shared"]:
                    print(f"Removing platform: {item.name}")
                    self._safe_rmtree(item)

    def cleanup_cpp_files(self) -> None:
        """Remove *.cpp files but keep *.hpp.cpp files and essential WASM files to match Docker setup."""
        print(
            "Removing *.cpp files (but keeping *.hpp.cpp files and essential WASM platform files)..."
        )

        # Essential files that must be preserved for compilation
        essential_files = {
            # Core FastLED files needed for linking
            "FastLED.cpp",
            "bitswap.cpp",
            "cled_controller.cpp",
            "colorpalettes.cpp",
            "crgb.cpp",
            "hsv2rgb.cpp",
            "lib8tion.cpp",
            "noise.cpp",
            "platforms.cpp",
            "power_mgt.cpp",
            "rgbw.cpp",
            "simplex.cpp",
            "transpose8x1_noinline.cpp",
            "wiring.cpp",
            # WASM platform files needed for linking
            "js.cpp",
            "js_bindings.cpp",
            "active_strip_data.cpp",
            "engine_listener.cpp",
            "fastspi_wasm.cpp",
            "fs_wasm.cpp",
            "timer.cpp",
            "ui.cpp",
        }

        files_to_remove = []
        for cpp_file in self.fastled_src.rglob("*.cpp"):
            if (
                not cpp_file.name.endswith(".hpp.cpp")
                and cpp_file.name not in essential_files
            ):
                files_to_remove.append(cpp_file)
            elif cpp_file.name in essential_files:
                print(
                    f"Preserving essential file: {cpp_file.relative_to(self.fastled_src)}"
                )

        # Remove files in batches to handle potential locking issues
        for cpp_file in files_to_remove:
            try:
                print(f"Removing: {cpp_file.relative_to(self.fastled_src)}")
                # Make file writable on Windows
                if os.name == "nt":
                    try:
                        cpp_file.chmod(0o777)
                    except (OSError, PermissionError):
                        pass
                cpp_file.unlink()
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not remove {cpp_file}: {e}")

    def normalize_line_endings(self) -> None:
        """Normalize line endings to Unix format."""
        print("Normalizing line endings...")

        file_patterns = [
            "*.c*",
            "*.h",
            "*.hpp",
            "*.sh",
            "*.js",
            "*.mjs",
            "*.css",
            "*.txt",
            "*.html",
            "*.toml",
        ]

        for pattern in file_patterns:
            for file_path in self.fastled_src.rglob(pattern):
                if file_path.is_file():
                    try:
                        # Read and normalize line endings
                        content = file_path.read_bytes()
                        normalized_content = content.replace(b"\r\n", b"\n")
                        if content != normalized_content:
                            file_path.write_bytes(normalized_content)
                    except Exception as e:
                        print(f"Warning: Could not normalize {file_path}: {e}")

    def install(self, force: bool = False) -> None:
        """Install FastLED with cleanup to match Docker environment.

        Args:
            force: Force reinstallation even if already installed
        """
        if not force and self.is_installed():
            print(f"FastLED already installed at {self.install_dir}")
            return

        print(f"Installing FastLED to {self.install_dir}")

        # Download and extract
        self.download_and_extract()

        # Apply the same cleanup as in Docker
        self.cleanup_platforms()
        self.cleanup_cpp_files()
        self.normalize_line_endings()

        # Verify installation
        if not self.is_installed():
            # List what's actually in the src directory for debugging
            if self.fastled_src.exists():
                print(f"Contents of {self.fastled_src}:")
                for item in self.fastled_src.iterdir():
                    print(f"  {item.name}")
            else:
                print(f"FastLED src directory {self.fastled_src} does not exist")

            raise RuntimeError(
                f"FastLED installation failed - FastLED.h not found in {self.fastled_src}"
            )

        print(f"✅ FastLED successfully installed to {self.install_dir}")

        # Update source timestamp after successful installation (only when actual installation occurred)
        from fastled_wasm_compiler.timestamp_utils import get_timestamp_manager

        timestamp_manager = get_timestamp_manager()
        timestamp_manager.update_source_timestamp()


def get_fastled_downloader(install_dir: Path | None = None) -> FastLEDDownloader:
    """Get a configured FastLED downloader instance."""
    return FastLEDDownloader(install_dir)


def ensure_fastled_installed(force: bool = False) -> Path:
    """Ensure FastLED is installed and return the source path.

    Args:
        force: Force reinstallation even if already installed

    Returns:
        Path to FastLED source directory
    """
    downloader = get_fastled_downloader()
    downloader.install(force=force)
    return downloader.fastled_src
