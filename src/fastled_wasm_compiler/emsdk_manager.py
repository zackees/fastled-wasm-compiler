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

import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import httpx

from fastled_wasm_compiler.paths import EMSDK_ROOT


class EmsdkPlatform:
    """Platform information for EMSDK binary selection."""

    def __init__(
        self, name: str, display_name: str, archive_pattern: str, platform_name: str
    ):
        self.name = name
        self.display_name = display_name
        self.archive_pattern = archive_pattern
        self.platform_name = platform_name


class EmsdkManager:
    """Manages EMSDK installation and environment setup."""

    BASE_URL = "https://fastled.github.io/emsdk-binaries/"

    # Platform mapping for binary selection
    PLATFORMS = {
        ("Linux", "x86_64"): EmsdkPlatform(
            "ubuntu-latest", "Ubuntu Linux", "emsdk-ubuntu-latest", "ubuntu"
        ),
        ("Darwin", "arm64"): EmsdkPlatform(
            "macos-arm64", "macOS Apple Silicon", "emsdk-macos-arm64", "macos-arm64"
        ),
        ("Darwin", "x86_64"): EmsdkPlatform(
            "macos-x86_64", "macOS Intel", "emsdk-macos-x86_64", "macos-x86_64"
        ),
        ("Windows", "AMD64"): EmsdkPlatform(
            "windows-latest", "Windows", "emsdk-windows-latest", "windows"
        ),
        ("Windows", "x86_64"): EmsdkPlatform(
            "windows-latest", "Windows", "emsdk-windows-latest", "windows"
        ),
    }

    def __init__(self, install_dir: Path | None = None, cache_dir: Path | None = None):
        """Initialize EMSDK Manager.

        Args:
            install_dir: Directory to install EMSDK to. Defaults to environment-driven EMSDK_ROOT
            cache_dir: Directory to cache downloads. Defaults to .cache/emsdk-binaries
        """
        self.install_dir = install_dir or Path(EMSDK_ROOT).parent
        self.cache_dir = cache_dir or (Path.cwd() / ".cache" / "emsdk-binaries")
        self.emsdk_dir = self.install_dir / "emsdk"
        self.platform_info = self._detect_platform()

        # Ensure directories exist
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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

    def _download_split_archive_cached(
        self, base_pattern: str, temp_dir: Path
    ) -> list[Path]:
        """Download split archive parts using cache to avoid re-downloads.

        Args:
            base_pattern: Base pattern for archive files (e.g., "emsdk-windows-latest")
            temp_dir: Temporary directory for reconstruction

        Returns:
            List of file paths in temp_dir ready for reconstruction
        """
        # Create cache subdirectory for this platform
        platform_cache = self.cache_dir / self.platform_info.platform_name
        platform_cache.mkdir(parents=True, exist_ok=True)

        # Build the platform directory URL based on platform_name
        platform_dir = f"{self.platform_info.platform_name}/"
        base_url = urljoin(self.BASE_URL, platform_dir)

        temp_files = []

        # Download or copy reconstruction script
        reconstruct_script = f"{base_pattern}-reconstruct.sh"
        cached_script = platform_cache / reconstruct_script
        temp_script = temp_dir / reconstruct_script

        if not cached_script.exists():
            script_url = urljoin(base_url, reconstruct_script)
            try:
                self._download_file(script_url, cached_script)
                print(f"Downloaded and cached: {reconstruct_script}")
            except Exception as e:
                print(f"Could not download reconstruction script: {e}")
        else:
            print(f"Using cached: {reconstruct_script}")

        if cached_script.exists():
            shutil.copy2(cached_script, temp_script)
            temp_files.append(temp_script)

        # Download or copy manifest file
        manifest_file = f"{base_pattern}-manifest.txt"
        cached_manifest = platform_cache / manifest_file
        temp_manifest = temp_dir / manifest_file

        if not cached_manifest.exists():
            manifest_url = urljoin(base_url, manifest_file)
            try:
                self._download_file(manifest_url, cached_manifest)
                print(f"Downloaded and cached: {manifest_file}")
            except Exception as e:
                print(f"Could not download manifest: {e}")
        else:
            print(f"Using cached: {manifest_file}")

        if cached_manifest.exists():
            shutil.copy2(cached_manifest, temp_manifest)
            temp_files.append(temp_manifest)

        # Download or copy split archive parts
        part_suffixes = ["aa", "ab", "ac", "ad", "ae", "af", "ag", "ah"]

        for suffix in part_suffixes:
            part_name = f"{base_pattern}.tar.xz.part{suffix}"
            cached_part = platform_cache / part_name
            temp_part = temp_dir / part_name

            if not cached_part.exists():
                part_url = urljoin(base_url, part_name)
                try:
                    self._download_file(part_url, cached_part)
                    print(f"Downloaded and cached: {part_name}")
                except Exception as e:
                    print(f"Part {suffix} not available: {e}")
                    break  # Stop when we hit a missing part

            if cached_part.exists():
                print(f"Using cached: {part_name}")
                shutil.copy2(cached_part, temp_part)
                temp_files.append(temp_part)
            else:
                break  # Stop if this part doesn't exist

        if not temp_files:
            raise RuntimeError(f"No archive files found for pattern {base_pattern}")

        return temp_files

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
        """Install EMSDK from pre-built binaries.

        Args:
            force: Force reinstallation even if already installed
        """
        if not force and self.is_installed():
            print(f"EMSDK already installed at {self.emsdk_dir}")
            return

        print(f"Installing EMSDK for {self.platform_info.display_name}")

        # Clean up existing installation if forcing
        if force and self.emsdk_dir.exists():
            print("Removing existing installation...")
            shutil.rmtree(self.emsdk_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            print("Downloading EMSDK archive...")
            self._download_split_archive_cached(
                self.platform_info.archive_pattern, temp_path
            )

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

    def get_env_vars(self) -> dict[str, str]:
        """Get environment variables needed for EMSDK.

        Returns:
            Dictionary of environment variables
        """
        if not self.is_installed():
            raise RuntimeError("EMSDK not installed. Call install() first.")

        # Get current environment as base
        env_vars = dict(os.environ)

        # Add EMSDK-specific paths directly without sourcing bash script
        emsdk_dir = self.emsdk_dir
        upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

        # Find actual node directory
        node_paths = list(emsdk_dir.glob("node/*/bin"))
        if node_paths:
            node_bin = str(node_paths[0])
        else:
            node_bin = ""

        # Update PATH to include EMSDK tools
        current_path = env_vars.get("PATH", "")
        new_path_parts = [
            str(upstream_emscripten),
            str(emsdk_dir),
        ]
        if node_bin:
            new_path_parts.append(node_bin)

        if current_path:
            new_path_parts.append(current_path)

        # Add our specific paths and settings
        env_vars.update(
            {
                "EMSDK": str(self.emsdk_dir),
                "EMSDK_NODE": node_bin if node_bin else str(emsdk_dir / "node"),
                "PATH": os.pathsep.join(new_path_parts),
                "CCACHE_DIR": str(Path.home() / ".fastled-ccache"),
                "CCACHE_MAXSIZE": "1G",
            }
        )

        return env_vars

    def get_tool_paths(self) -> dict[str, Path]:
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

    def setup_environment(self) -> dict[str, str]:
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

    def create_wrapper_scripts(self, output_dir: Path) -> dict[str, Path]:
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


def get_emsdk_manager(
    install_dir: Path | None = None, cache_dir: Path | None = None
) -> EmsdkManager:
    """Get a configured EMSDK manager instance."""
    return EmsdkManager(install_dir, cache_dir)


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
