# compile the fastled library in all three modes
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/debug --debug
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/quick --quick
# RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/release --release

import argparse
import subprocess
import sys
from dataclasses import dataclass


def _get_cmd(src: str, build: str, build_dir: str) -> list[str]:
    """Get the command to run based on the build mode."""
    assert build in ["debug", "quick", "release"], f"Invalid build mode: {build}"
    cmd_list: list[str] = [
        "python3",
        "/misc/compile_lib.py",
        "--src",
        src,
        "--out",
        build_dir,
        f"--{build}",
    ]
    return cmd_list


@dataclass
class Args:
    src: str
    out: str

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
        args = parser.parse_args()
        return Args(src=args.src, out=args.out)


def main() -> int:
    """Main entry point for the template_python_cmd package."""
    args: Args = Args.parse_args()
    src = args.src
    out = args.out
    build_modes = ["debug", "quick", "release"]

    for build_mode in build_modes:
        print(f"Building {build_mode} in {out}/{build_mode}...")
        build_out = f"{out}/{build_mode}"
        cmd = _get_cmd(src=src, build=build_mode, build_dir=build_out)
        cmd_str = subprocess.list2cmdline(cmd)
        print(f"Running command: {cmd_str}")
        proc = subprocess.Popen(
            cmd,
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
    print("All processes finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
