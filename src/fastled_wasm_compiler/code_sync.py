import shutil
import subprocess
import time
import warnings
from pathlib import Path
from typing import Callable

from fastled_wasm_server.compile_lock import COMPILE_LOCK

# from src\fastled_wasm_compiler\compile_all_libs.py
from fastled_wasm_compiler.compile_all_libs import compile_all_libs

TIME_START = time.time()

_HAS_RSYNC = shutil.which("rsync") is not None
# _ENABLED = os.environ.get("FASTLED_COMPILER_CODE_SYNC", "0") == "1"
_ENABLED = True

_DST_ROOT = Path("/git/fastled")
_DST_SRC = _DST_ROOT / "fastled" / "src"


def _sync_src_to_target(
    src: Path, dst: Path, callback_on_changed: Callable[[], None] | None = None
) -> bool:
    """Sync the volume mapped source directory to the FastLED source directory."""
    if not _ENABLED:
        warnings.warn("Code Sync is specifically disabled")
        return False
    if not _HAS_RSYNC:
        warnings.warn("rsync not found, skipping sync")
        return False

    assert (src / "FastLED.h").exists(), f"Expected FastLED.h not found at {src}"

    suppress_print = (
        TIME_START + 30 > time.time()
    )  # Don't print during initial volume map.
    if not src.exists():
        # Volume is not mapped in so we don't rsync it.
        print(f"Skipping rsync, as fastled src at {src} doesn't exist")
        return False
    try:
        exclude_hidden = "--exclude=.*/"  # suppresses folders like .mypy_cache/
        print("\nSyncing source directories...")
        with COMPILE_LOCK:
            # Use rsync to copy files, preserving timestamps and deleting removed files
            proc: subprocess.Popen = subprocess.Popen(
                [
                    "rsync",
                    "-av",
                    "--info=NAME",
                    "--delete",
                    f"{src}/",
                    f"{dst}/",
                    exclude_hidden,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            assert proc.stdout is not None

            line: bytes
            changed = False
            for line in proc.stdout:
                line = line.strip()
                linestr = line.decode(errors="replace")
                suffix = linestr.split(".")[-1]
                if suffix in ["cpp", "h", "hpp", "ino", "py", "js", "html", "css"]:
                    if not suppress_print:
                        print(f"Changed file: {linestr}")
                    changed = True
            proc.wait()
            proc.stdout.close()
            if proc.returncode != 0:
                print(f"Error syncing directories: {proc.stdout}\n\n{proc.stderr}")
                return False
            # Check if any files were changed
            if changed:
                if not suppress_print:
                    print("FastLED code had updates")
                if callback_on_changed:
                    callback_on_changed()
                return True

    except subprocess.CalledProcessError as e:
        print(f"Error syncing directories: {e.stdout}\n\n{e.stderr}")
    except Exception as e:
        print(f"Error syncing directories: {e}")
    return False


def _find_src_dir(src: Path) -> Path | None:
    """Find the FastLED source directory in the given path."""
    if (src / "FastLED.h").exists():
        return src
    elif (src / "fastled" / "src" / "FastLED.h").exists():
        return src / "fastled" / "src"
    else:
        print(f"Volume mapped source is not a valid FastLED source directory: {src}")
        return None


class CodeSync:

    def __init__(self):
        self.rsync_dest_root_src = Path("/git/fastled/fastled/src")

    def update_and_compile_core(
        self,
        updater_src_path: Path,
    ) -> bool:
        """Sync the volume mapped source directory to the FastLED source directory."""

        if not _ENABLED:
            warnings.warn("Code Sync is specifically disabled")
            return False
        if not _HAS_RSYNC:
            warnings.warn("rsync not found, skipping sync")
            return False

        src: Path | None = _find_src_dir(updater_src_path)
        if not src:
            print(
                f"Volume mapped source is not a valid FastLED source directory: {updater_src_path}"
            )
            return False

        expected_fastled_h = Path(src / "FastLED.h")
        if not expected_fastled_h.exists():
            print(f"Expected FastLED.h not found at {expected_fastled_h}")
            return False

        def callback_if_changed(src=src, dst=self.rsync_dest_root_src) -> None:
            # This is called when the source directory is updated
            # We need to compile all libs after the rsync
            print("Compiling all libs after rsync")
            # Compile all libs
            # from fastled_wasm_compiler.compile_all_libs import compile_all_libs
            # compile_all_libs(src, self.rsync_dest_root_src)
            compile_all_libs(
                str(src),
                str(dst),
                build_modes=["debug", "quick", "release"],
            )

        out = _sync_src_to_target(
            src, self.rsync_dest_root_src, callback_on_changed=callback_if_changed
        )

        return out

    # def sync_source_directory_if_volume_is_mapped(
    #     self,
    #     callback: Callable[[], None] | None = None,
    # ) -> bool:
    #     """Sync the volume mapped source directory to the FastLED source directory."""
    #     if not _ENABLED:
    #         warnings.warn("Code Sync is specifically disabled")
    #         return False
    #     if not self.volume_mapped_src.exists():
    #         # Volume is not mapped in so we don't rsync it.
    #         print("Skipping rsync, as fastled src volume not mapped")
    #         return False
    #     print("Syncing source directories because host is mapped in")
    #     out: bool = self.sync_src_to_target(callback=callback)
    #     return out
