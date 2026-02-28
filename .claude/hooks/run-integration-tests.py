"""SessionEnd hook: run integration tests when a Claude Code session ends."""

import json
import subprocess
import sys


def main() -> None:
    hook_input = json.loads(sys.stdin.read())
    cwd = hook_input.get("cwd", ".")

    print("Running integration tests (Docker full build)...", file=sys.stderr)
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/integration/test_full_build.py", "-v", "--durations=0", "-s"],
        cwd=cwd,
    )

    if result.returncode == 0:
        print("Integration tests passed", file=sys.stderr)
    else:
        print(f"Integration tests failed with exit code {result.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
