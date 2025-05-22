# compile the fastled library in all three modes
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/debug --debug
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/quick --quick
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/release --release

import argparse
import subprocess
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass


def _get_cmd(build: str) -> list[str]:
    """Get the command to run based on the build mode."""
    assert build in ["debug", "quick", "release"], f"Invalid build mode: {build}"
    cmd_list: list[str] = [
        "/build/build_lib.py",
        f"--{build}",
    ]
    return cmd_list


@dataclass
class Args:
    src: str
    out: str
    builds: list[str]

    @staticmethod
    def parse_args() -> "Args":
        parser = argparse.ArgumentParser(description="Compile FastLED for WASM")
        parser.add_argument(
            "--src",
            type=str,
            required=True,
            help="Path to FastLED source directory",
        )
        parser.add_argument(
            "--out",
            type=str,
            required=True,
            help="Output directory for build files",
        )
        parser.add_argument(
            "--builds",
            type=str,
            default="debug,quick,release",
        )
        args = parser.parse_args()
        args.builds = args.builds.split(",")
        return Args(src=args.src, out=args.out, builds=args.builds)


# def compile_all_libs_old(
#     src: str, out: str, build_modes: list[str] | None = None
# ) -> int:
#     start_time = time.time()
#     build_modes = build_modes or ["debug", "quick", "release"]
#     build_times: dict[str, float] = OrderedDict()

#     for build_mode in build_modes:
#         build_start_time = time.time()
#         print(f"Building {build_mode} in {out}/{build_mode}...")
#         build_out = f"{out}/{build_mode}"
#         cmd = _get_cmd(src=src, build=build_mode, build_dir=build_out)
#         cmd_str = subprocess.list2cmdline(cmd)
#         print(f"Running command: {cmd_str}")
#         proc = subprocess.Popen(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#         )
#         assert proc is not None, f"Failed to start process for {build_mode}"
#         # stream out stdout
#         assert proc.stdout is not None
#         line: bytes
#         for line in proc.stdout:
#             linestr = line.decode(errors="replace")
#             print(linestr, end="")
#         proc.stdout.close()
#         proc.wait()
#         print(f"Process {proc.pid} finished with return code {proc.returncode}")
#         if proc.returncode != 0:
#             print(f"Process {proc.pid} failed with return code {proc.returncode}")
#             return proc.returncode
#         diff = time.time() - build_start_time
#         build_times[build_mode] = diff
#     print("All processes finished successfully.")
#     end_time = time.time()
#     elapsed_time = end_time - start_time
#     print(f"Total time taken: {elapsed_time:.2f} seconds")
#     for mode, duration in build_times.items():
#         print(f"  {mode} build time: {duration:.2f} seconds")
#     return 0


def compile_all_libs(src: str, out: str, build_modes: list[str] | None = None) -> int:
    start_time = time.time()
    build_modes = build_modes or ["debug", "quick", "release"]
    build_times: dict[str, float] = OrderedDict()

    for build_mode in build_modes:
        build_start_time = time.time()
        print(f"Building {build_mode} in {out}/{build_mode}...")
        cmd = _get_cmd(build=build_mode)
        cmd_str = subprocess.list2cmdline(cmd)
        print(f"Running command: {cmd_str}")
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert proc is not None, f"Failed to start process for {build_mode}"
        # stream out stdout
        assert proc.stdout is not None
        line: bytes
        for line in proc.stdout:
            linestr = line.decode(errors="replace")
            print(linestr, end="")
        proc.stdout.close()
        proc.wait()
        print(f"Process {proc.pid} finished with return code {proc.returncode}")
        if proc.returncode != 0:
            print(f"Process {proc.pid} failed with return code {proc.returncode}")
            return proc.returncode
        diff = time.time() - build_start_time
        build_times[build_mode] = diff
    print("All processes finished successfully.")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken: {elapsed_time:.2f} seconds")
    for mode, duration in build_times.items():
        print(f"  {mode} build time: {duration:.2f} seconds")
    return 0


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    args: Args = Args.parse_args()
    src = args.src
    out = args.out
    print(f"Compiling all libraries from {src} to {out}")
    # Compile all libraries
    return_code = compile_all_libs(args.src, args.out, args.builds)
    if return_code != 0:
        print(f"Compilation failed with return code {return_code}")
        return return_code
    print("Compilation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
