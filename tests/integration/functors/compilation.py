"""Compilation-related test functors."""

from pathlib import Path

from .base import Functor


class CompilationSuccessFunctor(Functor):
    """Verify compilation success message in output."""

    def __init__(self):
        super().__init__(
            name="Compilation Success",
            description="Verify compilation completed successfully",
        )

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        full_output = "\n".join(output_lines)

        # Check for various success indicators
        success_patterns = [
            "compilation completed",
            "compilation successful",
            "build successful",
            "done",
        ]

        for pattern in success_patterns:
            if pattern.lower() in full_output.lower():
                self.passed = True
                return True

        self.error_message = "No compilation success message found in output"
        return False


class BuildFlagsVerificationFunctor(Functor):
    """Verify build flags are correctly applied."""

    def __init__(self, build_mode: str):
        super().__init__(
            name=f"Build Flags ({build_mode})",
            description=f"Verify {build_mode} mode compilation flags are present",
        )
        self.build_mode = build_mode

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        full_output = "\n".join(output_lines)

        # Check for build mode in output
        if f"Build mode: {self.build_mode}" not in full_output:
            # Try alternative patterns
            if (
                f"--{self.build_mode}" not in full_output
                and self.build_mode not in full_output.lower()
            ):
                self.error_message = (
                    f"Build mode '{self.build_mode}' not found in output"
                )
                return False

        # Mode-specific flag checks
        if self.build_mode == "debug":
            if "-g3" not in full_output or "-O0" not in full_output:
                self.error_message = "Debug flags (-g3, -O0) not found"
                return False
        elif self.build_mode == "release":
            if "-O3" not in full_output:
                self.error_message = "Release optimization flag (-O3) not found"
                return False

        self.passed = True
        return True
