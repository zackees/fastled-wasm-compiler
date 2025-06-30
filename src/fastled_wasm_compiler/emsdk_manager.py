"""
EMSDK Manager for FastLED WASM Compiler

This module handles the migration from Docker-based EMSDK to platform-specific
pre-built binaries from https://fastled.github.io/emsdk-binaries/

Key responsibilities:
- Platform detection and binary selection
- Download and extraction of split archives
- Environment setup and path management
- Toolchain validation
"""

import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx


class EmsdkPlatform:
    """Platform information for EMSDK binary selection."""

    def __init__(self, name: str, display_name: str, archive_pattern: str):
        self.name = name
        self.display_name = display_name
        self.archive_pattern = archive_pattern


class EmsdkManager:
    """Manages EMSDK installation and environment setup."""

    BASE_URL = "https://fastled.github.io/emsdk-binaries/"

    # Platform mapping for binary selection
    PLATFORMS = {
        ("Linux", "x86_64"): EmsdkPlatform(
            "ubuntu-latest", "Ubuntu Linux", "emsdk-ubuntu-latest"
        ),
        ("Darwin", "arm64"): EmsdkPlatform(
            "macos-arm64", "macOS Apple Silicon", "emsdk-macos-arm64"
        ),
        ("Darwin", "x86_64"): EmsdkPlatform(
            "macos-x86_64", "macOS Intel", "emsdk-macos-x86_64"
        ),
        ("Windows", "AMD64"): EmsdkPlatform(
            "windows-latest", "Windows", "emsdk-windows-latest"
        ),
        ("Windows", "x86_64"): EmsdkPlatform(
            "windows-latest", "Windows", "emsdk-windows-latest"
        ),
    }

    def __init__(self, install_dir: Optional[Path] = None):
        """Initialize EMSDK manager.

        Args:
            install_dir: Directory to install EMSDK. Defaults to ~/.fastled-emsdk
        """
        self.install_dir = install_dir or Path.home() / ".fastled-emsdk"
        self.emsdk_dir = self.install_dir / "emsdk"
        self.platform_info = self._detect_platform()

    def _detect_platform(self) -> EmsdkPlatform:
        """Detect current platform and return appropriate EMSDK platform info."""
        system = platform.system()
        machine = platform.machine()

        # Normalize machine names
        if machine in ("AMD64", "x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("arm64", "aarch64"):
            machine = "arm64"

        platform_key = (system, machine)

        if platform_key not in self.PLATFORMS:
            supported = ", ".join(f"{k[0]}-{k[1]}" for k in self.PLATFORMS.keys())
            raise RuntimeError(
                f"Unsupported platform {system}-{machine}. Supported: {supported}"
            )

        return self.PLATFORMS[platform_key]

    def is_installed(self) -> bool:
        """Check if EMSDK is already installed and functional."""
        if not self.emsdk_dir.exists():
            return False

        # Check for key files
        emsdk_env = self.emsdk_dir / "emsdk_env.sh"
        emcc_path = self.emsdk_dir / "upstream" / "emscripten" / "emcc"

        # On Windows, check for .bat extension too
        if platform.system() == "Windows":
            emcc_path_bat = emcc_path.with_suffix(".bat")
            return emsdk_env.exists() and (emcc_path.exists() or emcc_path_bat.exists())

        return emsdk_env.exists() and emcc_path.exists()

    def _download_file(self, url: str, destination: Path) -> None:
        """Download a file from URL to destination path."""
        print(f"Downloading {url} -> {destination}")

        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=300
            ) as response:
                response.raise_for_status()

                with open(destination, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            # Basic validation for downloaded files
            if destination.suffix in (".xz", ".tar"):
                if destination.stat().st_size < 1000:  # Too small to be valid
                    raise RuntimeError(
                        f"Downloaded file {destination} appears corrupted (too small)"
                    )

        except Exception as e:
            if destination.exists():
                destination.unlink()  # Clean up partial download
            raise RuntimeError(f"Failed to download {url}: {e}") from e

    def _download_split_archive(
        self, base_pattern: str, download_dir: Path
    ) -> List[Path]:
        """Download split archive parts and reconstruction script.

        Args:
            base_pattern: Base pattern like "emsdk-ubuntu-latest"
            download_dir: Directory to download files to

        Returns:
            List of downloaded file paths
        """
        downloaded_files = []

        # Download split parts (we don't know how many, so try until we fail)
        part_suffix = "a"
        part_num = 1

        while part_num <= 10:  # Safety limit
            if part_num == 1:
                part_file = f"{base_pattern}.tar.xz.parta{part_suffix}"
            else:
                part_file = f"{base_pattern}.tar.xz.parta{'a' * part_num}"

            url = urljoin(self.BASE_URL, f"{self.platform_info.name}/{part_file}")
            dest_path = download_dir / part_file

            try:
                self._download_file(url, dest_path)
                downloaded_files.append(dest_path)
                part_num += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break  # No more parts
                raise

        if not downloaded_files:
            # Try the alternate naming scheme
            part_letters = ["aa", "ab", "ac", "ad", "ae"]
            for letter in part_letters:
                part_file = f"{base_pattern}.tar.xz.part{letter}"
                url = urljoin(self.BASE_URL, f"{self.platform_info.name}/{part_file}")
                dest_path = download_dir / part_file

                try:
                    self._download_file(url, dest_path)
                    downloaded_files.append(dest_path)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        break
                    raise

        # Download reconstruction script and manifest
        for suffix in ["-reconstruct.sh", "-manifest.txt"]:
            filename = f"{base_pattern}{suffix}"
            url = urljoin(self.BASE_URL, f"{self.platform_info.name}/{filename}")
            dest_path = download_dir / filename

            try:
                self._download_file(url, dest_path)
                downloaded_files.append(dest_path)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    print(f"Warning: {filename} not found, continuing...")
                else:
                    raise

        return downloaded_files

    def _reconstruct_archive(self, download_dir: Path, base_pattern: str) -> Path:
        """Reconstruct split archive into complete tar.xz file."""
        reconstruct_script = download_dir / f"{base_pattern}-reconstruct.sh"
        target_archive = download_dir / f"{base_pattern}.tar.xz"

        if reconstruct_script.exists():
            # Use the reconstruction script
            print(f"Running reconstruction script: {reconstruct_script}")
            reconstruct_script.chmod(0o755)

            # On Windows, use bash to execute .sh scripts
            if platform.system() == "Windows":
                cmd = ["bash", str(reconstruct_script)]
            else:
                cmd = [str(reconstruct_script)]

            result = subprocess.run(
                cmd, cwd=download_dir, capture_output=True, text=True
            )

            if result.returncode != 0:
                print(f"Reconstruction script failed: {result.stderr}")
                # Fall back to manual reconstruction
            elif target_archive.exists():
                return target_archive

        # Manual reconstruction: concatenate all parts
        print("Performing manual archive reconstruction...")
        part_files = sorted(
            [
                f
                for f in download_dir.iterdir()
                if f.name.startswith(base_pattern) and ".tar.xz.part" in f.name
            ]
        )

        if not part_files:
            raise RuntimeError(f"No archive parts found for {base_pattern}")

        with open(target_archive, "wb") as output:
            for part_file in part_files:
                print(f"  Adding {part_file.name}")
                with open(part_file, "rb") as part:
                    shutil.copyfileobj(part, output)

        return target_archive

    def install(self, force: bool = False) -> None:
        """Download and install EMSDK for the current platform.

        Args:
            force: Force reinstallation even if already installed
        """
        if self.is_installed() and not force:
            print(f"EMSDK already installed at {self.emsdk_dir}")
            return

        print(f"Installing EMSDK for {self.platform_info.display_name}")

        # Create installation directory
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # Clean existing installation if forcing
        if force and self.emsdk_dir.exists():
            shutil.rmtree(self.emsdk_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download split archive files
            print("Downloading EMSDK archive...")
            downloaded_files = self._download_split_archive(
                self.platform_info.archive_pattern, temp_path
            )

            if not downloaded_files:
                raise RuntimeError("Failed to download any EMSDK files")

            # Reconstruct complete archive
            print("Reconstructing archive...")
            archive_path = self._reconstruct_archive(
                temp_path, self.platform_info.archive_pattern
            )

            # Extract archive
            print(f"Extracting {archive_path}...")
            try:
                with tarfile.open(archive_path, "r:xz") as tar:
                    tar.extractall(self.install_dir)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to extract EMSDK archive {archive_path}. The archive may be corrupted. Please try again or check the source at {self.BASE_URL}"
                ) from e

        if not self.is_installed():
            # Provide helpful error message with fallback suggestions
            error_msg = f"""
EMSDK installation verification failed.

This could be due to:
1. Corrupted or malformed binary archives from {self.BASE_URL}
2. Platform detection issues
3. Incomplete download

Suggested solutions:
1. Try again with force=True: manager.install(force=True)
2. Check the EMSDK binaries manually at {self.BASE_URL}
3. File an issue at https://github.com/zackees/fastled-wasm-compiler/issues

Platform detected: {self.platform_info.display_name}
Archive pattern: {self.platform_info.archive_pattern}
Install directory: {self.install_dir}
"""
            raise RuntimeError(error_msg.strip())

        print(f"EMSDK successfully installed to {self.emsdk_dir}")

    def get_env_vars(self) -> Dict[str, str]:
        """Get environment variables needed for EMSDK."""
        if not self.is_installed():
            raise RuntimeError("EMSDK not installed. Call install() first.")

        # Read emsdk_env.sh to get environment setup
        env_script = self.emsdk_dir / "emsdk_env.sh"
        if not env_script.exists():
            raise RuntimeError(f"EMSDK environment script not found: {env_script}")

        # Execute the environment script and capture output
        result = subprocess.run(
            ["bash", "-c", f"source {env_script} && env"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to source EMSDK environment: {result.stderr}")

        # Parse environment variables
        env_vars = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value

        return env_vars

    def get_tool_paths(self) -> Dict[str, Path]:
        """Get paths to EMSDK tools."""
        if not self.is_installed():
            raise RuntimeError("EMSDK not installed. Call install() first.")

        upstream_bin = self.emsdk_dir / "upstream" / "emscripten"

        tools = {
            "emcc": upstream_bin / "emcc",
            "em++": upstream_bin / "em++",
            "emar": upstream_bin / "emar",
            "emranlib": upstream_bin / "emranlib",
        }

        # On Windows, add .bat extension
        if platform.system() == "Windows":
            for tool_name in tools:
                tools[tool_name] = tools[tool_name].with_suffix(".bat")

        # Verify tools exist
        missing_tools = [name for name, path in tools.items() if not path.exists()]
        if missing_tools:
            raise RuntimeError(f"Missing EMSDK tools: {missing_tools}")

        return tools

    def setup_environment(self) -> Dict[str, str]:
        """Setup environment for EMSDK usage.

        Returns:
            Dictionary of environment variables to set
        """
        if not self.is_installed():
            self.install()

        env_vars = self.get_env_vars()

        # Add our specific paths and settings
        env_vars.update(
            {
                "EMSDK": str(self.emsdk_dir),
                "EMSDK_NODE": str(self.emsdk_dir / "node"),
                "CCACHE_DIR": str(Path.home() / ".fastled-ccache"),
                "CCACHE_MAXSIZE": "1G",
            }
        )

        return env_vars

    def create_wrapper_scripts(self, output_dir: Path) -> Dict[str, Path]:
        """Create ccache wrapper scripts for EMSDK tools.

        Args:
            output_dir: Directory to create wrapper scripts

        Returns:
            Dictionary mapping tool names to wrapper script paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        tool_paths = self.get_tool_paths()
        wrapper_scripts = {}

        for tool_name, tool_path in tool_paths.items():
            if tool_name in ("emcc", "em++"):
                # Create ccache wrapper
                wrapper_name = f"ccache-{tool_name}"
                if platform.system() == "Windows":
                    wrapper_path = output_dir / f"{wrapper_name}.bat"
                    wrapper_content = f"""@echo off
ccache {tool_path} %*
"""
                else:
                    wrapper_path = output_dir / f"{wrapper_name}.sh"
                    wrapper_content = f"""#!/bin/bash
exec ccache {tool_path} "$@"
"""

                wrapper_path.write_text(wrapper_content)
                wrapper_path.chmod(0o755)
                wrapper_scripts[wrapper_name] = wrapper_path
            else:
                # Direct tool reference
                wrapper_scripts[tool_name] = tool_path

        return wrapper_scripts


def get_emsdk_manager(install_dir: Optional[Path] = None) -> EmsdkManager:
    """Get a configured EMSDK manager instance."""
    return EmsdkManager(install_dir)


if __name__ == "__main__":
    # Command line interface for testing
    import argparse

    parser = argparse.ArgumentParser(description="EMSDK Manager")
    parser.add_argument("--install", action="store_true", help="Install EMSDK")
    parser.add_argument("--force", action="store_true", help="Force reinstall")
    parser.add_argument("--info", action="store_true", help="Show platform info")
    parser.add_argument("--env", action="store_true", help="Show environment variables")

    args = parser.parse_args()

    manager = get_emsdk_manager()

    if args.info:
        print(f"Platform: {manager.platform_info.display_name}")
        print(f"Archive pattern: {manager.platform_info.archive_pattern}")
        print(f"Install directory: {manager.install_dir}")
        print(f"Installed: {manager.is_installed()}")

    if args.install:
        manager.install(force=args.force)

    if args.env:
        if manager.is_installed():
            env_vars = manager.setup_environment()
            for key, value in sorted(env_vars.items()):
                print(f"{key}={value}")
        else:
            print("EMSDK not installed")
