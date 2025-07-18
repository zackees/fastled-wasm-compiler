"""
Direct emscripten toolchain compilation bypassing platformio.

This module provides functions to compile sketches directly using emscripten tools,
which is faster and more reliable than using platformio for WASM compilation.
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from fastled_wasm_compiler.compilation_flags import get_compilation_flags
from fastled_wasm_compiler.paths import BUILD_ROOT, get_fastled_source_path
from fastled_wasm_compiler.streaming_timestamper import StreamingTimestamper


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format (bytes, k, MB, GB)."""
    if size_bytes == 0:
        return "0 bytes"

    # Define the thresholds and units (decimal, not binary)
    units = ["bytes", "k", "MB", "GB", "TB"]
    threshold = 1000.0

    # Find the appropriate unit
    unit_index = 0
    size = float(size_bytes)

    while size >= threshold and unit_index < len(units) - 1:
        size /= threshold
        unit_index += 1

    # Format based on unit
    if unit_index == 0:  # bytes - show as integer
        return f"{int(size)} {units[unit_index]}"
    else:  # k, MB, GB - show with 1 decimal place
        return f"{size:.1f}{units[unit_index]}"


# --------------------------------------------------------------------------------------
# Timestamped printing for real-time output
# --------------------------------------------------------------------------------------


class TimestampedPrinter:
    """A class that provides timestamped printing functionality."""

    def __init__(self):
        self.timestamper = StreamingTimestamper()

    def tprint(self, *args: Any, **kwargs: Any) -> None:
        """Print with timestamp prefix for real-time output."""
        # Convert all arguments to a single string like print() does
        message = " ".join(str(arg) for arg in args)

        # Check if message already has a timestamp (e.g., "0.25 Warning!" or "12.34 Something")
        # If so, just indent it instead of adding our own timestamp
        if re.match(r"^\s*\d+\.\d+\s", message):
            # Message already has a timestamp, just indent it
            indented_message = "  " + message
            print(indented_message, **kwargs)
        else:
            # Normal timestamping
            timestamped_message = self.timestamper.timestamp_line(message)
            print(timestamped_message, **kwargs)


# --------------------------------------------------------------------------------------
# Mold daemon management
# --------------------------------------------------------------------------------------


def _start_mold_daemon() -> None:
    """Start mold daemon if mold is the selected linker."""
    linker = os.environ.get("LINKER", "lld")
    if linker != "mold":
        return

    try:
        subprocess.Popen(
            ["mold", "--run-daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("🚀 Mold daemon started for faster linking")
    except Exception as e:
        print(f"⚠️  Failed to start mold daemon: {e}")


# --------------------------------------------------------------------------------------
# Helper function
# --------------------------------------------------------------------------------------
# NOTE: We want to stream compiler/linker output _as it happens_ instead of buffering the
# entire output and printing it afterwards.  This helper runs the given command with
# `subprocess.Popen`, merges stdout/stderr, prints each line immediately (prefixed for
# context), then returns a `subprocess.CompletedProcess` so callers can still inspect the
# captured output and return-code just like they did with `subprocess.run`.


def _run_cmd_and_stream(
    cmd: list[str], printer: TimestampedPrinter | None = None
) -> subprocess.CompletedProcess:
    """Run command and return the completed process.

    Args:
        cmd: Command split into a list suitable for *subprocess*.
        printer: Optional timestamped printer for real-time output (linking only)

    Returns:
        A subprocess.CompletedProcess with stdout and the process' exit code.
    """
    # Run with real-time streaming output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,  # Line buffered
    )

    output_lines = []
    assert process.stdout is not None

    if printer:
        # Real-time streaming mode (for linking)
        has_output = False

        for line in process.stdout:
            line_clean = line.rstrip()
            output_lines.append(line)

            if line_clean:  # Only show non-empty lines
                if not has_output:
                    # Show header only when we actually have output
                    printer.tprint("📤 Linker output:")
                    has_output = True

                printer.tprint(f"    {line_clean}")
    else:
        # Capture mode (for compilation - used in parallel threads)
        for line in process.stdout:
            output_lines.append(line)

    # Wait for process to complete
    process.wait()

    # Return a CompletedProcess-like object
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=process.returncode,
        stdout="".join(output_lines),
        stderr=None,
    )


# Use environment-variable driven FastLED source path
# In Docker container, this should be set to "/git/fastled/src"
# On host system, this will use the default from paths.py
FASTLED_SRC_STR = get_fastled_source_path()

# Ensure it's an absolute path for Docker container
if not FASTLED_SRC_STR.startswith("/"):
    FASTLED_SRC_STR = f"/{FASTLED_SRC_STR}"

CC = "/build_tools/ccache-emcc.sh"
CXX = "/build_tools/ccache-emcxx.sh"

# NOTE: Compilation flags now centralized in compilation_flags.toml
# This ensures sketch and library compilation use compatible flags

# NOTE: Linking flags now centralized in compilation_flags.toml
# This ensures sketch and library compilation use compatible flags


def analyze_source_for_pch_usage(src_file: Path) -> tuple[bool, bool]:
    """
    Analyze a source file to determine if we can use precompiled headers.
    If we can use PCH and headers need to be removed, modifies the file in place.

    Returns:
        (can_use_pch, headers_removed):
        - can_use_pch: True if we can inject PCH (no defines before FastLED.h)
        - headers_removed: True if FastLED.h/Arduino.h includes were removed from the file
    """
    try:
        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Could not read {src_file}: {e}")
        return False, False

    lines = content.splitlines()

    # Track what we find
    fastled_include_line = None
    arduino_include_line = None
    has_defines_before_fastled = False

    # Scan through the file line by line
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check for FastLED.h include
        if re.match(r'^\s*#\s*include\s*[<"]FastLED\.h[>"]', line):
            fastled_include_line = i
            break  # Found FastLED.h, stop scanning

        # Check for Arduino.h include
        if re.match(r'^\s*#\s*include\s*[<"]Arduino\.h[>"]', line):
            arduino_include_line = i
            continue

        # Check for #define statements
        if re.match(r"^\s*#\s*define\s+", line):
            has_defines_before_fastled = True
            continue

        # Check for other preprocessor directives that might affect compilation
        if re.match(r"^\s*#\s*(ifdef|ifndef|if|pragma)", line):
            has_defines_before_fastled = True
            continue

    # If no FastLED.h found, we can't use PCH
    if fastled_include_line is None:
        return False, False

    # If there are defines before FastLED.h, we can't safely use PCH
    if has_defines_before_fastled:
        return False, False

    # We can use PCH! Check if we need to remove headers
    headers_to_remove = []
    if fastled_include_line is not None:
        headers_to_remove.append(fastled_include_line)
    if arduino_include_line is not None:
        headers_to_remove.append(arduino_include_line)

    if not headers_to_remove:
        # Can use PCH but no headers to remove
        return True, False

    # Remove headers (in reverse order to maintain line numbers)
    modified_lines = lines.copy()
    for line_num in sorted(headers_to_remove, reverse=True):
        del modified_lines[line_num]

    # Write the modified content back to the file
    try:
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("\n".join(modified_lines))
        return True, True
    except Exception as e:
        print(f"Warning: Could not modify {src_file}: {e}")
        return False, False


def compile_cpp_to_obj(
    src_file: Path,
    build_mode: str,
) -> tuple[subprocess.CompletedProcess, Path, str]:
    import time

    start_time = time.time()
    build_dir = BUILD_ROOT / build_mode.lower()
    obj_file = build_dir / f"{src_file.stem}.o"
    os.makedirs(build_dir, exist_ok=True)

    # Get compilation flags from centralized configuration
    flags_loader = get_compilation_flags()
    fastled_src_path = get_fastled_source_path()

    flags = flags_loader.get_full_compilation_flags(
        compilation_type="sketch",
        build_mode=build_mode,
        fastled_src_path=fastled_src_path,
        strict_mode=False,  # Could be made configurable later
    )

    # Get just the build mode flags for display
    mode_flags = flags_loader.get_build_mode_flags(build_mode)

    # Build output messages for later display

    # Track removed files for cleaner display
    removed_files = []

    # Analyze source file for intelligent PCH usage (available in all modes)
    pch_file = build_dir / "fastled_pch.h"
    can_use_pch = False
    headers_removed = False

    if pch_file.exists():
        can_use_pch, headers_removed = analyze_source_for_pch_usage(src_file)

        if can_use_pch:
            # Use PCH
            flags.extend(["-include", str(pch_file)])

            if headers_removed:
                removed_files.append(src_file.name)

    # cmd = [CXX, "-o", obj_file.as_posix(), *flags, str(src_file)]
    cmd: list[str] = []
    cmd.extend([CXX])
    cmd.append("-c")
    cmd.extend(["-x", "c++"])
    cmd.extend(["-o", obj_file.as_posix()])
    cmd.extend(flags)
    cmd.append(str(src_file))

    # Run compilation and capture output
    cp = _run_cmd_and_stream(cmd)

    # Calculate timing
    end_time = time.time()
    duration = end_time - start_time

    # Build final output in the desired order
    final_output = []

    # 1. Status line
    if cp.returncode == 0:
        final_output.append(
            f"✅ COMPILED: {src_file.name} → {obj_file.name} (success) in {duration:.2f} seconds"
        )
    else:
        final_output.append(
            f"❌ FAILED: {src_file.name} → {obj_file.name} (exit code: {cp.returncode}) in {duration:.2f} seconds"
        )

    # 2. Build command
    final_output.append("🔨 Build command:")
    final_output.append("  " + subprocess.list2cmdline(cmd))

    # 3. Mode-specific flags
    final_output.append(
        f"🔧 Mode-specific flags: {' '.join(mode_flags) if mode_flags else 'none'}"
    )

    # 4. PCH optimization if applicable
    if pch_file.exists() and can_use_pch:
        final_output.append(
            f"🚀 PCH OPTIMIZATION APPLIED: Using precompiled header {pch_file.name}"
        )
        if removed_files:
            final_output.append(
                "    ✂️ Removed: FastLED.h/Arduino.h includes from source files"
            )
            for i, filename in enumerate(removed_files, 1):
                final_output.append(f"         [{i}] {filename}")

    # 5. Compiler output only if there are errors or important messages
    has_compiler_output = (cp.stdout and cp.stdout.strip()) or (
        cp.stderr and cp.stderr.strip()
    )
    if has_compiler_output:
        final_output.append("📤 Compiler output:")
        if cp.stdout:
            for line in cp.stdout.splitlines():
                if line.strip():
                    final_output.append(f"[emcc] {line}")
        if cp.stderr:
            for line in cp.stderr.splitlines():
                if line.strip():
                    final_output.append(f"[emcc] {line}")

    return (cp, obj_file, "\n".join(final_output))


def compile_sketch(sketch_dir: Path, build_mode: str) -> Exception | None:
    # Create a timestamped printer for this compilation run
    printer = TimestampedPrinter()

    # Determine output directory first
    output_dir = BUILD_ROOT / build_mode.lower()

    printer.tprint("\n🚀 Starting FastLED sketch compilation (no-platformio mode)")
    printer.tprint("🔊 VERBOSE MODE: Showing detailed emcc/linker output")
    printer.tprint(f"📁 Sketch directory: {sketch_dir}")
    printer.tprint(f"🔧 Build mode: {build_mode}")
    printer.tprint(f"📂 Output directory: {output_dir}")

    # Start mold daemon for faster linking
    _start_mold_daemon()

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    printer.tprint(f"✓ Output directory prepared: {output_dir}")

    # Prepare debug info for debug mode
    dwarf_file = None
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        printer.tprint(
            f"🐛 Debug mode: DWARF debug info will be generated at {dwarf_file}"
        )

    # Gather all .cpp and .ino files in sketch dir
    sources = list(sketch_dir.glob("*.cpp")) + list(sketch_dir.glob("*.ino"))
    if not sources:
        raise RuntimeError(f"No .cpp or .ino files found in {sketch_dir}")

    printer.tprint("\n📋 Source file discovery:")
    printer.tprint(f"✓ Found {len(sources)} source file(s):")
    for i, src in enumerate(sources, 1):
        printer.tprint(f"  {i}. {src.name} ({src.stat().st_size} bytes)")

    # Now print out the entire build flags group from centralized configuration:
    flags_loader = get_compilation_flags()
    fastled_src_path = get_fastled_source_path()

    # Get flags for the current build mode for display
    compilation_flags = flags_loader.get_full_compilation_flags(
        compilation_type="sketch",
        build_mode=build_mode,
        fastled_src_path=fastled_src_path,
        strict_mode=False,
    )

    linker = os.environ.get("LINKER", "lld")
    link_flags = flags_loader.get_full_linking_flags(
        compilation_type="sketch",
        linker=linker,
    )

    printer.tprint("\n🔧 Compilation configuration (from compilation_flags.toml):")
    printer.tprint("📋 CXX_FLAGS:")
    for i, flag in enumerate(compilation_flags):
        printer.tprint(f"  {i+1:2d}. {flag}")
    printer.tprint("\n📋 LINK_FLAGS:")
    for i, flag in enumerate(link_flags):
        printer.tprint(f"  {i+1:2d}. {flag}")
    printer.tprint(f"\n📋 Sources: {' '.join(str(s) for s in sources)}")
    printer.tprint(f"📋 Sketch directory: {sketch_dir}")

    # Determine which FastLED library to link against based on volume mapped source availability
    from fastled_wasm_compiler.paths import (
        can_use_thin_lto,
        is_volume_mapped_source_defined,
    )

    use_thin = can_use_thin_lto()

    if use_thin:
        # Use thin archives
        lib_path = BUILD_ROOT / build_mode.lower() / "libfastled-thin.a"
        if is_volume_mapped_source_defined():
            printer.tprint(
                "Volume mapped source defined, NO_THIN_LTO=0: Using thin archive"
            )
        else:
            printer.tprint("Using thin archive")
    else:
        # Use regular archives
        lib_path = BUILD_ROOT / build_mode.lower() / "libfastled.a"
        if is_volume_mapped_source_defined():
            printer.tprint(
                "Volume mapped source defined, NO_THIN_LTO=1: Using regular archive"
            )
        else:
            printer.tprint("Volume mapped source not defined: Using regular archive")

    printer.tprint(f"\n📚 FastLED library: {lib_path}")

    if not lib_path.exists():
        printer.tprint(f"⚠️  Warning: FastLED library not found at {lib_path}")
    else:
        lib_size = lib_path.stat().st_size
        archive_type = "thin" if "thin" in lib_path.name else "regular"
        printer.tprint(
            f"✓ FastLED library found ({lib_size} bytes, {archive_type} archive)"
        )

    obj_files: list[Path] = []
    printer.tprint(f"\n🔨 Compiling {len(sources)} source files in parallel:")
    printer.tprint("=" * 80)

    # Use ThreadPoolExecutor to compile files in parallel
    max_workers = min(len(sources), os.cpu_count() or 4)  # Limit to available CPUs
    printer.tprint(f"🔧 Using {max_workers} worker threads for parallel compilation")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all compilation tasks
        future_to_src = {
            executor.submit(compile_cpp_to_obj, src_file, build_mode): src_file
            for src_file in sources
        }

        # Process completed compilations as they finish
        completed_count = 0

        try:
            for future in as_completed(future_to_src):
                src_file = future_to_src[future]
                completed_count += 1

                try:
                    cp, obj_file, output = future.result()

                    # Print the compilation result with count included
                    # Modify the output to include the count in the status line
                    output_lines = output.split("\n")
                    if output_lines:
                        # Update the first line (status line) to include the count
                        status_line = output_lines[0]
                        if "✅ COMPILED:" in status_line:
                            status_line = status_line.replace(
                                "✅ COMPILED:",
                                f"✅ COMPILED [{completed_count}/{len(sources)}]:",
                            )
                        elif "❌ FAILED:" in status_line:
                            status_line = status_line.replace(
                                "❌ FAILED:",
                                f"❌ FAILED [{completed_count}/{len(sources)}]:",
                            )
                        output_lines[0] = status_line

                        # Print each line
                        for line in output_lines:
                            if line.strip():
                                printer.tprint(line)

                    if cp.returncode != 0:
                        printer.tprint(f"❌ Error compiling {src_file}:")
                        # Cancel all remaining futures
                        for remaining_future in future_to_src:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        printer.tprint("🛑 Cancelling remaining compilation tasks...")
                        return RuntimeError(
                            f"Error compiling {src_file}: Compilation failed with exit code {cp.returncode}"
                        )
                    obj_size = obj_file.stat().st_size if obj_file.exists() else 0
                    printer.tprint(
                        f"  ✓ [{completed_count}/{len(sources)}] {src_file.name} → {obj_file.name} ({obj_size} bytes)"
                    )
                    obj_files.append(obj_file)
                except Exception as e:
                    printer.tprint(
                        f"❌ Exception during compilation of {src_file}: {e}"
                    )

                    # Cancel all remaining futures
                    for remaining_future in future_to_src:
                        if not remaining_future.done():
                            remaining_future.cancel()
                    printer.tprint("🛑 Cancelling remaining compilation tasks...")
                    return RuntimeError(
                        f"Exception during compilation of {src_file}: {e}"
                    )
        except KeyboardInterrupt:
            printer.tprint(
                "🛑 Compilation interrupted by user, cancelling all tasks..."
            )
            # Cancel all futures on keyboard interrupt
            for future in future_to_src:
                future.cancel()
            raise

    printer.tprint("-" * 80)
    printer.tprint(f"✅ All {len(sources)} source files compiled successfully")

    # Link everything into one JS+WASM module
    output_js = output_dir / "fastled.js"
    output_wasm = output_dir / "fastled.wasm"

    printer.tprint("\n🔗 Linking phase - Creating final WASM output:")
    printer.tprint("=" * 80)
    printer.tprint(f"✓ Linking {len(obj_files)} object file(s) into final output")

    total_obj_size = sum(obj.stat().st_size for obj in obj_files if obj.exists())
    printer.tprint(f"✓ Total object file size: {total_obj_size} bytes")

    # Build linking command with centralized flags
    flags_loader = get_compilation_flags()
    linker = os.environ.get("LINKER", "lld")
    link_flags = flags_loader.get_full_linking_flags(
        compilation_type="sketch",
        linker=linker,
        build_mode=build_mode,
    )

    # Add output file
    link_flags.extend(["-o", "fastled.js"])

    # Add debug-specific flags if needed
    if build_mode.lower() == "debug" and dwarf_file:
        link_flags.append(f"-gseparate-dwarf={dwarf_file}")

    cmd_link: list[str] = []
    cmd_link.extend([CXX])
    cmd_link.extend(link_flags)
    cmd_link.extend(map(str, obj_files))

    # Use volume mapped source aware archive selection
    use_thin = can_use_thin_lto()

    if build_mode.lower() == "debug":
        if use_thin:
            debug_lib = BUILD_ROOT / "debug" / "libfastled-thin.a"
        else:
            debug_lib = BUILD_ROOT / "debug" / "libfastled.a"
        cmd_link.append(str(debug_lib))
        archive_type = "thin" if use_thin else "regular"
        printer.tprint(
            f"🐛 Linking with debug FastLED library: {debug_lib} ({archive_type})"
        )
    elif build_mode.lower() == "release":
        if use_thin:
            release_lib = BUILD_ROOT / "release" / "libfastled-thin.a"
        else:
            release_lib = BUILD_ROOT / "release" / "libfastled.a"
        cmd_link.append(str(release_lib))
        archive_type = "thin" if use_thin else "regular"
        printer.tprint(
            f"🚀 Linking with release FastLED library: {release_lib} ({archive_type})"
        )
    elif build_mode.lower() == "quick":
        if use_thin:
            quick_lib = BUILD_ROOT / "quick" / "libfastled-thin.a"
        else:
            quick_lib = BUILD_ROOT / "quick" / "libfastled.a"
        cmd_link.append(str(quick_lib))
        archive_type = "thin" if use_thin else "regular"
        printer.tprint(
            f"⚡ Linking with quick FastLED library: {quick_lib} ({archive_type})"
        )
    else:
        raise ValueError(f"Invalid build mode: {build_mode}")
    cmd_link[cmd_link.index("-o") + 1] = str(output_js)
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        cmd_link.append(f"-gseparate-dwarf={dwarf_file}")

    # Run linker and capture output with timing
    import time

    link_start_time = time.time()
    cp = _run_cmd_and_stream(cmd_link, printer)
    link_end_time = time.time()
    link_duration = link_end_time - link_start_time

    # Show linking result with timing
    if cp.returncode != 0:
        printer.tprint(
            f"❌ LINKING FAILED: {output_js.name} (exit code: {cp.returncode}) in {link_duration:.2f} seconds"
        )
        printer.tprint("🔗 Build command:")
        printer.tprint(f"  {subprocess.list2cmdline(cmd_link)}")
        return RuntimeError(
            f"Error linking {output_js}: Linking failed with exit code {cp.returncode}"
        )
    else:
        printer.tprint(
            f"✅ LINKED: {output_js.name} (success) in {link_duration:.2f} seconds"
        )
        printer.tprint("🔗 Build command:")
        printer.tprint(f"  {subprocess.list2cmdline(cmd_link)}")

    printer.tprint("=" * 80)

    # Check and report output file sizes
    if output_js.exists():
        js_size = output_js.stat().st_size
        printer.tprint(
            f"✅ JavaScript output: {output_js} ({format_file_size(js_size)})"
        )
    else:
        printer.tprint(f"⚠️  JavaScript output not found: {output_js}")

    if output_wasm.exists():
        wasm_size = output_wasm.stat().st_size
        printer.tprint(
            f"✅ WebAssembly output: {output_wasm} ({format_file_size(wasm_size)})"
        )
    else:
        printer.tprint(f"⚠️  WebAssembly output not found: {output_wasm}")

    # Check for debug files in debug mode
    if build_mode.lower() == "debug":
        dwarf_file = output_dir / "fastled.wasm.dwarf"
        if dwarf_file.exists():
            dwarf_size = dwarf_file.stat().st_size
            printer.tprint(f"🐛 Debug info: {dwarf_file} ({dwarf_size} bytes)")
        else:
            printer.tprint(f"⚠️  Debug info not found: {dwarf_file}")

    printer.tprint(f"\n✅ Program built at: {output_js}")
    printer.tprint("🔊 VERBOSE BUILD COMPLETED: All emcc/linker calls shown above")

    return None


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a FastLED sketch into WASM using a static lib."
    )
    parser.add_argument(
        "--sketch",
        type=Path,
        required=True,
        help="Directory with example source files",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["debug", "quick", "release"],
        default="debug",
        help="Build mode: debug, quick, or release (default: debug)",
    )

    args = parser.parse_args()

    err = compile_sketch(args.sketch, args.mode)
    if isinstance(err, Exception):
        print(f"Compilation error: {err}")
        return 1
    assert err is None, f"Error was not None: {err}"
    return 0


if __name__ == "__main__":
    sys.exit(_main())
