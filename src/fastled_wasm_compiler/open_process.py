import subprocess

from fastled_wasm_compiler.print_banner import banner


def open_process(
    cmd_list: list[str], compiler_root: str, env: dict
) -> subprocess.Popen:
    print(banner("Build started with command:\n  " + subprocess.list2cmdline(cmd_list)))
    out = subprocess.Popen(
        cmd_list,
        cwd=compiler_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        env=env,
    )
    return out
