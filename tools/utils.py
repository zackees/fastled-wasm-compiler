"""
Utility functions for the tools directory.
These are copies of functions from the main package to avoid circular imports.
"""

import hashlib
from pathlib import Path


def hash_file(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def banner(msg: str) -> str:
    """
    Create a banner for the given message.
    Example:
    msg = "Hello, World!"
    print -> "#################"
             "# Hello, World! #"
             "#################"
    """
    lines = msg.split("\n")
    # Find the width of the widest line
    max_width = max(len(line) for line in lines)
    width = max_width + 4  # Add 4 for "# " and " #"

    # Create the top border
    banner = "\n" + "#" * width + "\n"

    # Add each line with proper padding
    for line in lines:
        padding = max_width - len(line)
        banner += f"# {line}{' ' * padding} #\n"

    # Add the bottom border
    banner += "#" * width + "\n"
    return banner


def print_banner(msg: str) -> None:
    """Prints a banner with the given message."""
    print(banner(msg))
