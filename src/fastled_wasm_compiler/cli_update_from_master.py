import logging
import platform
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from fastled_wasm_compiler.compiler import Compiler
from fastled_wasm_compiler.paths import FASTLED_SRC
from fastled_wasm_compiler.sync import sync_fastled

_FASTLED_SRC_STR = FASTLED_SRC.as_posix()
_FASTLED_SRC = Path(_FASTLED_SRC_STR)

_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    # Assume we are in testing mode and stip away the leading slash.
    _FASTLED_SRC_STR = (
        _FASTLED_SRC_STR[1:] if _FASTLED_SRC_STR.startswith("/") else _FASTLED_SRC_STR
    )
    _FASTLED_SRC = Path(_FASTLED_SRC_STR)

URL = "https://github.com/FastLED/FastLED/archive/refs/heads/master.zip"

_TIMEOUT = 60 * 5  # 5 minutes

_BUILD = False
_FORCE_LOGGING = False


# Create logger for this module
logger = logging.getLogger(__name__)


def _download(url: str, outpath: Path) -> None:
    """Download a file from a URL to a local path."""
    logger.info(f"Downloading {url} to {outpath}")
    with open(outpath, "wb") as f:
        response = httpx.get(url, follow_redirects=True, timeout=_TIMEOUT)
        content = response.content
        assert len(content) >= 10000, "Downloaded file is too small"
        f.write(content)
    logger.info("Download complete")


def _maybe_turn_on_logging() -> None:
    if _FORCE_LOGGING or __name__ == "__main__":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger.info("Starting FastLED update from master")


def main() -> int:
    """Main entry point for the script."""
    # Configure logging when running as main
    _maybe_turn_on_logging()

    if not _FASTLED_SRC.exists():
        logger.info(f"Creating FastLED source directory at {_FASTLED_SRC_STR}")
        _FASTLED_SRC.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using FastLED source directory: {_FASTLED_SRC_STR}")
    with TemporaryDirectory() as tmpdir:
        logger.info(f"Downloading FastLED from {URL}")
        # with open(f"{tmpdir}/fastled.zip", "wb") as f:
        target_zip = Path(tmpdir) / "fastled.zip"
        _download(URL, target_zip)
        logger.info("Download complete, extracting files")
        with zipfile.ZipFile(target_zip, "r") as zip_ref:
            # extra here because we only want the src directory
            logger.info(f"Extracting files to {tmpdir}")
            zip_ref.extractall(tmpdir)
            main_dir = Path(tmpdir) / "FastLED-master"
        tmp_src_root = Path(main_dir) / "src"
        expected_header = tmp_src_root / "FastLED.h"
        logger.info(f"Checking for FastLED.h at {expected_header}")
        assert (
            expected_header.exists()
        ), f"Expected header not found at {expected_header}"
        logger.info("FastLED.h found, proceeding with update")
        src = tmp_src_root
        if _BUILD:
            logger.info(f"Creating compiler with source from {src}")
            compiler = Compiler(volume_mapped_src=src)
            logger.info("Updating source code from master")
            result = compiler.update_src(src_to_merge_from=src)
            if result:
                logger.error(f"Error updating source: {result}")
                return 1
        else:
            dst = _FASTLED_SRC
            # move all files from src to dst
            sync_fastled(src, dst)
        logger.info("Source update completed successfully")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
