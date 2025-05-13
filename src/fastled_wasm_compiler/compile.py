import os
import subprocess
from pathlib import Path

from fastled_wasm_compiler.open_process import open_process
from fastled_wasm_compiler.print_banner import banner
from fastled_wasm_compiler.streaming_timestamper import StreamingTimestamper
from fastled_wasm_compiler.types import BuildMode

_PIO_VERBOSE = True


def _pio_compile_cmd_list(
    build_mode: BuildMode | None, disable_auto_clean: bool, verbose: bool
) -> list[str]:
    cmd_list = ["pio", "run"]
    if disable_auto_clean:
        cmd_list.append("--disable-auto-clean")
    if verbose:
        cmd_list.append("-v")
    if build_mode and build_mode == BuildMode.DEBUG:
        cmd_list.append("-t")
        cmd_list.append("debug")

    return cmd_list


def _new_compile_cmd_list(compiler_root: Path) -> list[str]:
    cmd_list = [
        "/bin/bash",
        "-c",
        (compiler_root / "build_fast.sh").as_posix(),
    ]
    return cmd_list


def compile(
    compiler_root: Path, build_mode: BuildMode, auto_clean: bool, no_platformio: bool
) -> int:
    print("Starting compilation process...")
    max_attempts = 1
    env = os.environ.copy()
    env["BUILD_MODE"] = build_mode.name
    print(banner(f"WASM is building in mode: {build_mode.name}"))
    cmd_list: list[str]
    if no_platformio:
        cmd_list = _new_compile_cmd_list(compiler_root)
    else:
        cmd_list = _pio_compile_cmd_list(build_mode, not auto_clean, _PIO_VERBOSE)

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Attempting compilation (attempt {attempt}/{max_attempts})...")
            print(f"Command: {subprocess.list2cmdline(cmd_list)}")
            process: subprocess.Popen = open_process(
                cmd_list=cmd_list,
                compiler_root=compiler_root.as_posix(),
                env=env,
            )
            assert process.stdout is not None

            # Create a new timestamper for this compilation attempt
            timestamper = StreamingTimestamper()

            # Process and print each line as it comes in with relative timestamp
            line: str
            for line in process.stdout:
                timestamped_line = timestamper.timestamp_line(line)
                print(timestamped_line)

            process.wait()

            print(banner("Compilation process Finsished."))

            if process.returncode == 0:
                print("\nCompilation successful.\n")
                return 0
            else:
                raise subprocess.CalledProcessError(process.returncode, ["pio", "run"])
        except subprocess.CalledProcessError:
            print(banner(f"Compilation failed on attempt {attempt}"))
            if attempt == max_attempts:
                print("Max attempts reached. Compilation failed.")
                return 1
            print("Retrying...")
    return 1
