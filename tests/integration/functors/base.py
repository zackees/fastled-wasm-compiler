"""Base class for all test functors."""

from pathlib import Path


class Functor:
    """Base class for all test validators."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.passed = False
        self.error_message = ""

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        """
        Analyze compilation output and return True if test passes.

        Args:
            output_lines: All stdout lines from compilation
            output_dir: Path to output directory with compiled artifacts

        Returns:
            True if validation passes, False otherwise
        """
        raise NotImplementedError

    def report(self) -> str:
        """Generate test result report."""
        status = "PASS" if self.passed else "FAIL"
        result = f"{status}: {self.name}\n"
        result += f"   Description: {self.description}\n"
        if not self.passed and self.error_message:
            result += f"   Error: {self.error_message}\n"
        return result
