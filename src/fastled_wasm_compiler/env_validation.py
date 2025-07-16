"""
Environment variable validation for FastLED WASM Compiler.

This module provides utilities to validate and manage required environment variables
for the compiler tools. Environment variables can be set directly or passed as
command line arguments.
"""

import argparse
import os
import sys
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    """Configuration for environment variables used by the compiler."""

    fastled_root: str
    fastled_source_path: str
    emsdk_path: str
    sketch_path: str
    volume_mapped_src: str | None

    def apply_to_environment(self) -> None:
        """Apply these settings to the current environment."""
        os.environ["ENV_FASTLED_ROOT"] = self.fastled_root
        os.environ["ENV_FASTLED_SOURCE_PATH"] = self.fastled_source_path
        os.environ["ENV_EMSDK_PATH"] = self.emsdk_path
        os.environ["ENV_SKETCH_ROOT"] = self.sketch_path

        # Only set ENV_VOLUME_MAPPED_SRC if it has a value (it's optional)
        if self.volume_mapped_src:
            os.environ["ENV_VOLUME_MAPPED_SRC"] = self.volume_mapped_src


def add_environment_arguments(parser: argparse.ArgumentParser) -> None:
    """Add environment variable arguments to an argument parser."""
    env_group = parser.add_argument_group("Environment Configuration")

    env_group.add_argument(
        "--fastled-root",
        help="FastLED root directory (ENV_FASTLED_ROOT)",
    )

    env_group.add_argument(
        "--fastled-source-path",
        help="FastLED source path (ENV_FASTLED_SOURCE_PATH)",
    )

    env_group.add_argument(
        "--emsdk-path",
        help="EMSDK path (ENV_EMSDK_PATH)",
    )

    env_group.add_argument(
        "--sketch-path",
        help="Sketch path (ENV_SKETCH_ROOT)",
    )

    env_group.add_argument(
        "--volume-mapped-src",
        help="Volume mapped source path (ENV_VOLUME_MAPPED_SRC) [optional]",
    )


def validate_and_get_environment(args: argparse.Namespace) -> EnvironmentConfig:
    """
    Validate that required environment variables are set, either from command line
    arguments or existing environment variables.

    Args:
        args: Parsed command line arguments

    Returns:
        EnvironmentConfig with validated values

    Raises:
        SystemExit: If required environment variables are missing
    """

    def get_env_value(
        arg_name: str, env_name: str, description: str, required: bool = True
    ) -> str | None:
        # Check command line argument first
        arg_value = getattr(args, arg_name.replace("-", "_"), None)
        if arg_value:
            return arg_value

        # Check environment variable
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value

        # Neither command line nor environment variable set
        if required:
            print(
                f"❌ Error: {description} must be set via --{arg_name} argument or {env_name} environment variable"
            )
            raise ValueError(
                f"❌ Error: {description} must be set via --{arg_name} argument or {env_name} environment variable"
            )
        else:
            # Optional variable, return empty string
            return None

    # Validate required environment variables
    fastled_root = get_env_value(
        "fastled-root", "ENV_FASTLED_ROOT", "FastLED root directory"
    )
    fastled_source_path = get_env_value(
        "fastled-source-path", "ENV_FASTLED_SOURCE_PATH", "FastLED source path"
    )
    emsdk_path = get_env_value("emsdk-path", "ENV_EMSDK_PATH", "EMSDK path")
    sketch_path = get_env_value("sketch-path", "ENV_SKETCH_ROOT", "Sketch path")

    # Optional environment variable
    volume_mapped_src = get_env_value(
        "volume-mapped-src",
        "ENV_VOLUME_MAPPED_SRC",
        "Volume mapped source path",
        required=False,
    )

    # Collect any missing required values
    missing_values = []
    if not fastled_root:
        missing_values.append("fastled-root (ENV_FASTLED_ROOT)")
    if not fastled_source_path:
        missing_values.append("fastled-source-path (ENV_FASTLED_SOURCE_PATH)")
    if not emsdk_path:
        missing_values.append("emsdk-path (ENV_EMSDK_PATH)")
    if not sketch_path:
        missing_values.append("sketch-path (ENV_SKETCH_ROOT)")

    if missing_values:
        print("\n❌ Missing required environment configuration:")
        for missing in missing_values:
            print(f"   - {missing}")
        print("\nSet these via command line arguments or environment variables.")
        print("Example:")
        print(
            "  fastled-wasm-compiler --fastled-root=/git/fastled --fastled-source-path=/git/fastled/src ..."
        )
        print("  OR")
        print("  export ENV_FASTLED_ROOT=/git/fastled")
        print("  export ENV_FASTLED_SOURCE_PATH=/git/fastled/src")
        print("  ...")
        print("\nNote: ENV_VOLUME_MAPPED_SRC is optional and can be omitted.")
        sys.exit(1)

    assert fastled_root is not None
    assert fastled_source_path is not None
    assert emsdk_path is not None
    assert sketch_path is not None

    return EnvironmentConfig(
        fastled_root=fastled_root,
        fastled_source_path=fastled_source_path,
        emsdk_path=emsdk_path,
        sketch_path=sketch_path,
        volume_mapped_src=volume_mapped_src,
    )


def ensure_environment_configured(args: argparse.Namespace) -> None:
    """
    Ensure environment is properly configured from arguments or environment variables.

    This function validates the environment configuration and applies it to the
    current process environment.

    Args:
        args: Parsed command line arguments containing potential environment overrides
    """
    config = validate_and_get_environment(args)
    config.apply_to_environment()
