import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler.open_process import open_process
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.types import BuildMode

# RUN python /misc/compile_sketch.py \
#   --example /examples/Blink/Blink.cpp \
#   --lib /build/debug/libfastled.a \
#   --out /build_examples/blink


def _new_compile_cmd_list(compiler_root: Path, build_mode: BuildMode) -> list[str]:
    # Use the compile_sketch.py module to compile the sketch directly
    cmd_list = [
        "python",
        "-m",
        "fastled_wasm_compiler.compile_sketch",
        "--sketch",
        str(compiler_root / "src"),  # The sketch source directory
        "--mode",
        build_mode.name.lower(),  # debug, quick, or release
    ]
    return cmd_list


def compile(
    compiler_root: Path,
    build_mode: BuildMode,
    auto_clean: bool,
    no_platformio: bool,
    profile_build: bool,
) -> int:

    print("Starting compilation process...")
    env = os.environ.copy()
    env["BUILD_MODE"] = build_mode.name
    print(banner(f"WASM is building in mode: {build_mode.name}"))
    if profile_build:
        env["EMPROFILE"] = "2"  # Profile linking

    if profile_build:
        print(banner("Enabling profiling for compilation."))
    else:
        print(
            banner(
                "Build process profiling is disabled\nuse --profile to get metrics on how long the build process took."
            )
        )

    # DEPRECATION: PlatformIO support has been removed
    if not no_platformio:
        print("⚠️  WARNING: PlatformIO build is deprecated and has been removed.")
        print(
            "⚠️  Automatically falling back to direct emcc compilation (--no-platformio mode)."
        )
        print("⚠️  Please update your build scripts to use --no-platformio explicitly.")
        print("⚠️  This fallback behavior will be removed in a future version.")
        no_platformio = True  # Force non-PlatformIO build

    # PlatformIO support has been completely removed - using native compilation only

    # Always use non-PlatformIO compilation now
    print(banner("Using direct emcc compilation"))
    print("✓ Using direct emscripten compiler calls")
    print(f"✓ Build mode: {build_mode.name}")
    print(f"✓ Compiler root: {compiler_root}")
    print("✓ Will use compile_sketch.py module for compilation")
    cmd_list = _new_compile_cmd_list(compiler_root, build_mode)
    print(f"✓ Direct compilation command prepared: {subprocess.list2cmdline(cmd_list)}")

    print(f"Command: {subprocess.list2cmdline(cmd_list)}")
    print(f"Command cwd: {compiler_root.as_posix()}")
    process: subprocess.Popen = open_process(
        cmd_list=cmd_list,
        compiler_root=compiler_root.as_posix(),
        env=env,
    )
    assert process.stdout is not None

    # Always use non-PlatformIO output handling (no timestamping since compile_sketch.py handles it)
    line: str
    for line in process.stdout:
        print(line.rstrip())

    process.wait()
    print(banner("Compilation process Finsished."))
    if process.returncode == 0:
        print("\nCompilation successful.\n")
        return 0
    else:
        # raise subprocess.CalledProcessError(process.returncode, ["pio", "run"])
        print(banner(f"Compilation failed with return code {process.returncode}.\n"))
        print("Check the output above for details.")
        return process.returncode
