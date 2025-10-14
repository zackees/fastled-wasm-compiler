"""Output file-related test functors."""

from pathlib import Path

from .base import Functor


class WASMFileSizeFunctor(Functor):
    """Verify WASM output file exists and has reasonable size."""

    def __init__(self, min_size: int = 1000):
        super().__init__(
            name="WASM Output Size",
            description=f"Verify fastled.wasm exists and is >= {min_size} bytes",
        )
        self.min_size = min_size

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        wasm_file = output_dir / "fastled.wasm"

        if not wasm_file.exists():
            self.error_message = f"WASM file not found at {wasm_file}"
            return False

        size = wasm_file.stat().st_size
        if size < self.min_size:
            self.error_message = (
                f"WASM file too small: {size} bytes (expected >= {self.min_size})"
            )
            return False

        self.passed = True
        return True


class ManifestExistsFunctor(Functor):
    """Verify manifest file was generated."""

    def __init__(self):
        super().__init__(
            name="Manifest File Exists",
            description="Verify files.json was generated",
        )

    def check(self, output_lines: list[str], output_dir: Path) -> bool:
        manifest_file = output_dir / "files.json"

        if not manifest_file.exists():
            self.error_message = f"Manifest file not found at {manifest_file}"
            return False

        # Verify it's not empty
        size = manifest_file.stat().st_size
        if size == 0:
            self.error_message = "Manifest file is empty"
            return False

        self.passed = True
        return True
