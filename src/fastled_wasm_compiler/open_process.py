import shutil
import subprocess

from fastled_wasm_compiler.print_banner import banner


def open_process(
    cmd_list: list[str], compiler_root: str, env: dict
) -> subprocess.Popen:
    print(banner("Build started with command:\n  " + subprocess.list2cmdline(cmd_list)))

    # Try to use stdbuf to force line buffering if available
    # This prevents compilation tools from switching to full buffering mode
    # when they detect output is being piped (not to a terminal)
    if shutil.which("stdbuf"):
        # stdbuf -oL forces line buffering for stdout
        # stdbuf -eL forces line buffering for stderr
        final_cmd = ["stdbuf", "-oL", "-eL"] + cmd_list
        print("✓ Using stdbuf to force line buffering for real-time output")
    else:
        final_cmd = cmd_list
        print("⚠ stdbuf not available - output may be buffered")

    out = subprocess.Popen(
        final_cmd,
        cwd=compiler_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,  # Line buffered on Python side
        env=env,
    )
    return out
