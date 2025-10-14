"""PCH-related test functors."""

import re
from pathlib import Path

from .base import Functor


class PCHEnabledFunctor(Functor):
    """Verify that PCH was used for files without #define."""

    def __init__(self):
        super().__init__(
            name="PCH Optimization Enabled",
            description="Verify helper.cpp used PCH (no #define before include)",
        )

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        full_output = "\n".join(output_lines)

        pattern = r"helper\.cpp.*PCH OPTIMIZATION.*Using precompiled header"
        if re.search(pattern, full_output, re.DOTALL):
            self.passed = True
            return True

        self.error_message = "PCH optimization message not found for helper.cpp"
        return False


class PCHDisabledFunctor(Functor):
    """Verify that PCH was disabled for files with #define."""

    def __init__(self):
        super().__init__(
            name="PCH Correctly Disabled",
            description="Verify config.cpp disabled PCH (#define before include)",
        )

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        full_output = "\n".join(output_lines)

        pattern = r"config\.cpp.*PCH DISABLED.*#define statements found before"
        if re.search(pattern, full_output, re.DOTALL):
            self.passed = True
            return True

        self.error_message = "Expected PCH disabled message for config.cpp not found"
        return False
