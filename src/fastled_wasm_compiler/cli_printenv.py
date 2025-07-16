"""
CLI module to print container environment variables.

This is useful for debugging and testing container configuration.
"""

import os
import sys


def main() -> int:
    """Print all environment variables and exit with code 0."""
    print("=== Container Environment Variables ===")

    # Print all environment variables in alphabetical order
    for key, value in sorted(os.environ.items()):
        print(f"{key}={value}")

    print("=== End Environment Variables ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
