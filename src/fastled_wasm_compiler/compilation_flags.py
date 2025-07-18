"""
Centralized compilation flags loader.

This module reads the compilation_flags.toml file and provides consistent
compilation flags for both sketch compilation and libfastled compilation.
"""

from pathlib import Path
from typing import Any, BinaryIO, cast

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python versions
    except ImportError:
        raise ImportError("TOML support required. Install with: pip install tomli")

from importlib.resources import files


class CompilationFlags:
    """Manages compilation flags from centralized TOML configuration."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize with optional custom config path."""
        self.config_path = config_path
        self._config: dict[str, Any] = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load TOML configuration file."""
        if self.config_path is not None:
            # Use custom config path
            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"Compilation flags config not found: {self.config_path}"
                )
            with open(self.config_path, "rb") as f:
                return tomllib.load(f)
        else:
            # Use package resource (default)
            try:
                package_files = files("fastled_wasm_compiler")
                config_file = package_files / "compilation_flags.toml"
                with cast(BinaryIO, config_file.open("rb")) as f:
                    return tomllib.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(
                    "Compilation flags config not found in package: compilation_flags.toml"
                )

    def get_base_flags(self) -> list[str]:
        """Get base compilation flags shared by all compilation."""
        flags = []
        flags.extend(self._config["base"]["defines"])
        flags.extend(self._config["base"]["compiler_flags"])
        return flags

    def get_include_flags(self, fastled_src_path: str) -> list[str]:
        """Get include flags with FastLED source path added."""
        flags = list(self._config["base"]["include_flags"])
        flags.extend(
            [
                f"-I{fastled_src_path}",
                f"-I{fastled_src_path}/platforms/wasm/compiler",
            ]
        )
        return flags

    def get_sketch_flags(self) -> list[str]:
        """Get sketch-specific compilation flags."""
        flags = []
        flags.extend(self._config["sketch"]["defines"])
        flags.extend(self._config["sketch"]["compiler_flags"])
        return flags

    def get_library_flags(self) -> list[str]:
        """Get library-specific compilation flags."""
        flags = []
        flags.extend(self._config["library"]["defines"])
        flags.extend(self._config["library"]["compiler_flags"])
        return flags

    def get_build_mode_flags(self, build_mode: str) -> list[str]:
        """Get build mode specific flags (debug, quick, release)."""
        build_mode_lower = build_mode.lower()
        if build_mode_lower not in self._config["build_modes"]:
            raise ValueError(f"Unknown build mode: {build_mode}")

        return list(self._config["build_modes"][build_mode_lower]["flags"])

    def get_build_mode_link_flags(self, build_mode: str) -> list[str]:
        """Get build mode specific linking flags."""
        build_mode_lower = build_mode.lower()
        if build_mode_lower not in self._config["build_modes"]:
            raise ValueError(f"Unknown build mode: {build_mode}")

        mode_config = self._config["build_modes"][build_mode_lower]
        return list(mode_config.get("link_flags", []))

    def get_strict_mode_flags(self) -> list[str]:
        """Get strict mode warning flags."""
        return list(self._config["strict_mode"]["flags"])

    def get_base_link_flags(self, linker: str = "lld") -> list[str]:
        """Get base linking flags with dynamic linker selection."""
        flags = list(self._config["linking"]["base"]["flags"])
        flags.insert(0, f"-fuse-ld={linker}")  # Add linker flag first
        return flags

    def get_sketch_link_flags(self) -> list[str]:
        """Get sketch-specific linking flags."""
        return list(self._config["linking"]["sketch"]["flags"])

    def get_library_link_flags(self) -> list[str]:
        """Get library-specific linking flags."""
        return list(self._config["linking"]["library"]["flags"])

    def get_full_compilation_flags(
        self,
        compilation_type: str,  # "sketch" or "library"
        build_mode: str,
        fastled_src_path: str,
        strict_mode: bool = False,
    ) -> list[str]:
        """Get complete compilation flags for a specific use case."""
        if compilation_type not in ["sketch", "library"]:
            raise ValueError(f"Invalid compilation type: {compilation_type}")

        flags = []

        # Base flags (common to all)
        flags.extend(self.get_base_flags())
        flags.extend(self.get_include_flags(fastled_src_path))

        # Type-specific flags
        if compilation_type == "sketch":
            flags.extend(self.get_sketch_flags())
        else:  # library
            flags.extend(self.get_library_flags())

        # Build mode flags
        flags.extend(self.get_build_mode_flags(build_mode))

        # Strict mode flags
        if strict_mode:
            flags.extend(self.get_strict_mode_flags())

        return flags

    def get_full_linking_flags(
        self,
        compilation_type: str,  # "sketch" or "library"
        linker: str = "lld",
        build_mode: str | None = None,
    ) -> list[str]:
        """Get complete linking flags for a specific use case."""
        if compilation_type not in ["sketch", "library"]:
            raise ValueError(f"Invalid compilation type: {compilation_type}")

        flags = []

        # Base linking flags
        flags.extend(self.get_base_link_flags(linker))

        # Type-specific linking flags
        if compilation_type == "sketch":
            flags.extend(self.get_sketch_link_flags())
        else:  # library
            flags.extend(self.get_library_link_flags())

        # Build mode specific linking flags
        if build_mode:
            flags.extend(self.get_build_mode_link_flags(build_mode))

        return flags


# Global instance for easy access
_flags_instance: CompilationFlags | None = None


def get_compilation_flags() -> CompilationFlags:
    """Get global compilation flags instance."""
    global _flags_instance
    if _flags_instance is None:
        _flags_instance = CompilationFlags()
    return _flags_instance


def reset_compilation_flags() -> None:
    """Reset global instance (useful for testing)."""
    global _flags_instance
    _flags_instance = None
