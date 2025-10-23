"""
Docker command discovery utility.

This module provides cross-platform support for locating the docker executable.
It searches in default installation locations on Windows, macOS, and Linux.
"""

import logging
import platform
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def find_docker_command() -> str:
    """
    Find the docker command in system PATH or default installation locations.

    This function:
    1. First tries to find docker in the system PATH (using shutil.which)
    2. If not found, searches common installation directories based on OS
    3. Returns the full path to the docker executable
    4. Raises RuntimeError if docker is not found

    Returns:
        str: The full path to the docker executable

    Raises:
        RuntimeError: If docker command is not found in PATH or default locations
    """
    # First try standard PATH lookup
    docker_path = shutil.which("docker")
    if docker_path:
        logger.debug(f"Found docker in PATH: {docker_path}")
        return docker_path

    logger.debug(
        "Docker not found in PATH, searching default installation locations..."
    )

    system = platform.system()

    if system == "Windows":
        docker_path = _find_docker_windows()
    elif system == "Darwin":  # macOS
        docker_path = _find_docker_macos()
    elif system == "Linux":
        docker_path = _find_docker_linux()
    else:
        raise RuntimeError(
            f"Unsupported operating system: {system}. "
            + "Unable to search for docker in default locations."
        )

    if docker_path:
        logger.debug(f"Found docker at: {docker_path}")
        return docker_path

    raise RuntimeError(
        "Docker command not found. Please ensure Docker is installed and available in PATH, "
        + "or check that Docker is installed in a standard location."
    )


def _find_docker_windows() -> str | None:
    """
    Find docker command on Windows.

    Windows docker installations are typically in:
    - C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe
    - C:\\Program Files (x86)\\Docker\\Docker\\resources\\bin\\docker.exe
    """
    logger.debug("Searching for docker on Windows...")

    common_paths = [
        Path("C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe"),
        Path("C:\\Program Files (x86)\\Docker\\Docker\\resources\\bin\\docker.exe"),
        Path.home()
        / "AppData"
        / "Local"
        / "Docker"
        / "Docker"
        / "resources"
        / "bin"
        / "docker.exe",
    ]

    for path in common_paths:
        if path.exists():
            logger.info(f"Found docker at: {path}")
            return str(path)
        logger.debug(f"Checked (not found): {path}")

    return None


def _find_docker_macos() -> str | None:
    """
    Find docker command on macOS.

    macOS docker installations are typically in:
    - /usr/local/bin/docker (Intel Macs, Docker Desktop)
    - /opt/homebrew/bin/docker (Apple Silicon Macs with Homebrew)
    - /Applications/Docker.app/Contents/Resources/bin/docker
    """
    logger.debug("Searching for docker on macOS...")

    common_paths = [
        Path("/usr/local/bin/docker"),  # Intel Macs
        Path("/opt/homebrew/bin/docker"),  # Apple Silicon with Homebrew
        Path(
            "/Applications/Docker.app/Contents/Resources/bin/docker"
        ),  # Docker Desktop
    ]

    for path in common_paths:
        if path.exists():
            logger.info(f"Found docker at: {path}")
            return str(path)
        logger.debug(f"Checked (not found): {path}")

    return None


def _find_docker_linux() -> str | None:
    """
    Find docker command on Linux.

    Linux docker installations are typically in:
    - /usr/bin/docker (most distributions)
    - /usr/local/bin/docker
    - /snap/bin/docker (snap installation)
    """
    logger.debug("Searching for docker on Linux...")

    common_paths = [
        Path("/usr/bin/docker"),
        Path("/usr/local/bin/docker"),
        Path("/snap/bin/docker"),  # Snap installation
    ]

    for path in common_paths:
        if path.exists():
            logger.info(f"Found docker at: {path}")
            return str(path)
        logger.debug(f"Checked (not found): {path}")

    return None


def check_docker_availability(docker_cmd: str | None = None) -> None:
    """
    Check if Docker is available and running.

    This function:
    1. Finds the docker command (using find_docker_command if not provided)
    2. Verifies the command is executable
    3. Checks if the Docker daemon is running

    Args:
        docker_cmd: Optional path to docker executable. If not provided, will search for it.

    Raises:
        RuntimeError: If docker is not found, not executable, or daemon is not running
    """
    if docker_cmd is None:
        docker_cmd = find_docker_command()

    try:
        # Check if docker command is executable
        result = subprocess.run(
            [docker_cmd, "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Docker command failed: {result.stderr}. "
                + "Please ensure Docker is properly installed."
            )

        logger.debug(f"Docker version: {result.stdout.strip()}")

        # Check if Docker daemon is running
        result = subprocess.run(
            [docker_cmd, "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            error_msg = (
                "Docker is installed but not running. "
                "Please start Docker Desktop or the Docker daemon."
            )
            if (
                "cannot connect" in result.stderr.lower()
                or "connection refused" in result.stderr.lower()
            ):
                error_msg += f"\nError details: {result.stderr.strip()}"
            raise RuntimeError(error_msg)

        logger.debug("Docker daemon is running")

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Docker command timed out. Docker may not be responding properly."
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"Docker executable not found at: {docker_cmd}. "
            + "Please ensure Docker is properly installed."
        )
