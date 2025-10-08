"""
Adapter to convert fastled-wasm-compiler's build_flags.toml
to FastLED's BuildFlags structure.

This module bridges the gap between our TOML format and the
BuildFlags class expected by native_compiler.Compiler.
"""

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from pathlib import Path

from .native_compiler import (
    ArchiveOptions,
    BuildFlags,
    BuildTools,
)


def load_wasm_compiler_flags(
    toml_path: Path, build_mode: str = "quick", strict_mode: bool = False
) -> BuildFlags:
    """
    Load fastled-wasm-compiler's build_flags.toml and convert to BuildFlags.

    Args:
        toml_path: Path to build_flags.toml
        build_mode: "debug", "quick", or "release"
        strict_mode: Enable strict mode warnings

    Returns:
        BuildFlags instance compatible with native_compiler.Compiler

    Raises:
        FileNotFoundError: If TOML file doesn't exist
        KeyError: If required sections are missing
    """
    if not toml_path.exists():
        raise FileNotFoundError(f"build_flags.toml not found: {toml_path}")

    with open(toml_path, "rb") as f:
        config = tomllib.load(f)

    # Extract tools (must exist after we add [tools] section)
    tools_config = config.get("tools", {})
    if not tools_config:
        raise KeyError(
            "Missing [tools] section in build_flags.toml. "
            + "This section is required for native compilation. "
            + "Please add: [tools] with cpp_compiler, archiver, linker, etc."
        )

    tools = BuildTools(
        cpp_compiler=tools_config["cpp_compiler"],
        linker=tools_config["linker"],
        archiver=tools_config["archiver"],
        c_compiler=tools_config["c_compiler"],
        objcopy=tools_config["objcopy"],
        nm=tools_config["nm"],
        strip=tools_config["strip"],
        ranlib=tools_config["ranlib"],
    )

    # Extract archive options
    archive_config = config.get("archive", {})
    if not archive_config:
        # Default archive settings
        archive = ArchiveOptions(
            flags="rcsD",  # Standard ar flags
            linux=None,
            windows=None,
            darwin=None,
        )
    else:
        archive = ArchiveOptions(
            flags=archive_config.get("flags", "rcsD"),
            linux=None,
            windows=None,
            darwin=None,
        )

        # Check for Emscripten-specific flags
        if "emscripten" in archive_config:
            emscripten_config = archive_config["emscripten"]
            # For Emscripten, use special flags on all platforms
            archive.flags = emscripten_config.get("flags", "rcs")

    # Combine flags from different sections
    all_section = config.get("all", {})
    library_section = config.get("library", {})
    mode_section = config.get(f"build_modes.{build_mode}", {})

    # Defines (remove -D prefix if present)
    defines = []
    for define in all_section.get("defines", []):
        if define.startswith("-D"):
            defines.append(define[2:])  # Remove -D
        else:
            defines.append(define)

    for define in library_section.get("defines", []):
        if define.startswith("-D"):
            defines.append(define[2:])
        else:
            defines.append(define)

    # Compiler flags
    compiler_flags = []
    compiler_flags.extend(all_section.get("compiler_flags", []))
    compiler_flags.extend(library_section.get("compiler_flags", []))
    compiler_flags.extend(mode_section.get("flags", []))

    # Include flags
    include_flags = all_section.get("include_flags", [])

    # Link flags
    linking_base = config.get("linking", {}).get("base", {})
    link_flags = linking_base.get("flags", [])
    link_flags.extend(mode_section.get("link_flags", []))

    # Strict mode flags
    strict_mode_config = config.get("strict_mode", {})
    strict_mode_flags = strict_mode_config.get("flags", [])

    return BuildFlags(
        defines=defines,
        compiler_flags=compiler_flags,
        include_flags=include_flags,
        link_flags=link_flags,
        strict_mode_flags=strict_mode_flags if strict_mode else [],
        tools=tools,
        archive=archive,
    )
