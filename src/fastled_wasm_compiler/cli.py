"""
Main entry point.
"""

import sys

from fastled_wasm_compiler.run import Args, run


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    args = Args.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
