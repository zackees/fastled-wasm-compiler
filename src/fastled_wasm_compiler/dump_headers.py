"""
Header Dumper for FastLED WASM Compiler

This module implements the --headers feature to dump all FastLED and WASM headers
to a specified output directory with organized structure.
"""

import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from .emsdk_manager import get_emsdk_manager
from .fastled_downloader import ensure_fastled_installed


class HeaderDumper:
    """Manages dumping of FastLED and WASM headers to an organized output directory."""

    # Header file extensions to include
    HEADER_EXTENSIONS = [".h", ".hpp", ".hh", ".hxx"]

    # Source file extensions to include when --add-src is used
    SOURCE_EXTENSIONS = [".c", ".cpp", ".cc", ".cxx", ".ino"]

    # Files to exclude from header collection
    EXCLUDE_PATTERNS = [
        "*.gch",  # Precompiled headers
        "*.pch",  # Precompiled headers
        "*.bak",  # Backup files
        "*~",  # Backup files
        ".*",  # Hidden files
    ]

    def __init__(self, output_dir: Path, include_source: bool = False):
        """Initialize HeaderDumper.

        Args:
            output_dir: Directory where headers will be dumped, or zip file path if ends with .zip
            include_source: Whether to include source files in addition to headers
        """
        self.output_dir = output_dir
        self.include_source = include_source
        self.is_zip_output = str(output_dir).lower().endswith(".zip")
        self.emsdk_manager = get_emsdk_manager()
        self.fastled_src = ensure_fastled_installed()

    def dump_all_headers(
        self,
    ) -> Dict[str, Any]:
        """Dump all headers and return manifest.

        Returns:
            Dictionary with header categories and lists of relative file paths
        """
        if self.is_zip_output:
            print(f"🔧 Dumping headers to zip archive: {self.output_dir}")
        else:
            print(f"🔧 Dumping headers to: {self.output_dir}")

        if self.include_source:
            print("📦 Including source files in dump")

        start_time = time.time()

        # Use temporary directory if creating a zip
        if self.is_zip_output:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_output = Path(temp_dir) / "headers"
                return self._dump_headers_to_directory(temp_output, start_time)
        else:
            return self._dump_headers_to_directory(self.output_dir, start_time)

    def _dump_headers_to_directory(
        self, work_dir: Path, start_time: float
    ) -> Dict[str, Any]:
        """Internal method to dump headers to a working directory.

        Args:
            work_dir: Working directory for header collection
            start_time: Start time for performance measurement

        Returns:
            Dictionary with header categories and lists of relative file paths
        """
        # Temporarily set output_dir to work_dir for internal methods
        original_output_dir = self.output_dir
        original_is_zip = self.is_zip_output

        try:
            self.output_dir = work_dir
            self.is_zip_output = (
                False  # Temporarily disable zip mode for internal operations
            )

            # Create output directory structure
            self._create_output_structure()

            # Collect headers from all sources
            manifest: Dict[str, Any] = {
                "fastled": self._dump_fastled_headers(),
                "wasm": self._dump_wasm_headers(),
                "arduino": self._dump_arduino_headers(),
            }

            # Add metadata to manifest
            manifest["metadata"] = {
                "timestamp": time.time(),
                "fastled_src_path": str(self.fastled_src),
                "emsdk_path": str(self.emsdk_manager.emsdk_dir),
                "include_source": self.include_source,
                "total_files": sum(
                    len(files) for files in manifest.values() if isinstance(files, list)
                ),
            }

            # Write manifest file
            self._write_manifest(manifest)

            # Create zip archive if needed
            if original_is_zip:
                self._create_zip_archive(work_dir, original_output_dir)

            elapsed = time.time() - start_time
            total_files = manifest["metadata"]["total_files"]

            if original_is_zip:
                print(
                    f"✅ Headers archived to zip: {total_files} files in {elapsed:.2f} seconds"
                )
            else:
                print(
                    f"✅ Header dump complete: {total_files} files in {elapsed:.2f} seconds"
                )

            return manifest

        finally:
            # Restore original settings
            self.output_dir = original_output_dir
            self.is_zip_output = original_is_zip

    def _create_output_structure(self) -> None:
        """Create the organized output directory structure."""
        directories = [
            self.output_dir / "fastled" / "src",
            self.output_dir / "wasm" / "system",
            self.output_dir / "wasm" / "emscripten",
            self.output_dir / "wasm" / "c++",
            self.output_dir / "arduino",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _dump_fastled_headers(self) -> List[str]:
        """Dump FastLED library headers from src/** directories only.

        Returns:
            List of relative paths of copied FastLED headers
        """
        print("📦 Collecting FastLED headers from src/** directories...")

        if not self.fastled_src.exists():
            print(f"⚠️  FastLED source not found at {self.fastled_src}")
            return []

        fastled_output = self.output_dir / "fastled"
        copied_files = []

        # self.fastled_src already points to the src directory (e.g., /git/fastled/src)
        # No need to append another "src"
        fastled_src_dir = self.fastled_src
        if not fastled_src_dir.exists():
            print(f"⚠️  FastLED src directory not found at {fastled_src_dir}")
            return []

        # Find header files (and optionally source files) in FastLED src
        extensions = self.HEADER_EXTENSIONS.copy()
        if self.include_source:
            extensions.extend(self.SOURCE_EXTENSIONS)

        header_files = self._find_files_in_directory(fastled_src_dir, extensions)
        print(f"   Found {len(header_files)} FastLED files in src/")

        for header_file in header_files:
            # Determine relative path within FastLED src
            rel_path = header_file.relative_to(fastled_src_dir)

            # Copy maintaining the src directory structure
            dest_path = fastled_output / "src" / rel_path

            # Copy the file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(header_file, dest_path)
            copied_files.append(str(dest_path.relative_to(self.output_dir)))

        print(f"   Copied {len(copied_files)} FastLED files")
        return copied_files

    def _dump_wasm_headers(self) -> List[str]:
        """Dump WASM/Emscripten headers from src/** directories only.

        Returns:
            List of relative paths of copied WASM headers
        """
        print("🌐 Collecting WASM/Emscripten headers...")

        if not self.emsdk_manager.is_installed():
            print("⚠️  EMSDK not installed, installing now...")
            self.emsdk_manager.install()

        # WASM system headers are in the sysroot
        sysroot_include = (
            self.emsdk_manager.emsdk_dir
            / "upstream"
            / "emscripten"
            / "cache"
            / "sysroot"
            / "include"
        )

        if not sysroot_include.exists():
            print(f"⚠️  WASM system headers not found at {sysroot_include}")
            return []

        wasm_output = self.output_dir / "wasm"
        copied_files = []

        # Find header files (and optionally source files) in WASM includes
        extensions = self.HEADER_EXTENSIONS.copy()
        if self.include_source:
            extensions.extend(self.SOURCE_EXTENSIONS)

        header_files = self._find_files_in_directory(sysroot_include, extensions)
        print(f"   Found {len(header_files)} WASM files")

        for header_file in header_files:
            # Determine relative path within sysroot
            rel_path = header_file.relative_to(sysroot_include)

            # Organize by subdirectory
            if "emscripten" in rel_path.parts:
                # Emscripten-specific APIs
                dest_path = wasm_output / "emscripten" / rel_path
            elif "c++" in str(rel_path) or "bits" in rel_path.parts:
                # C++ standard library headers
                dest_path = wasm_output / "c++" / rel_path
            else:
                # Standard C headers and other system headers
                dest_path = wasm_output / "system" / rel_path

            # Copy the header file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(header_file, dest_path)
            copied_files.append(str(dest_path.relative_to(self.output_dir)))

        print(f"   Copied {len(copied_files)} WASM files")
        return copied_files

    def _dump_arduino_headers(self) -> List[str]:
        """Dump Arduino compatibility headers from src/** directories only.

        Returns:
            List of relative paths of copied Arduino headers
        """
        print("🔌 Collecting Arduino compatibility headers...")

        # Arduino compatibility headers are in the FastLED platforms/wasm/compiler directory
        arduino_src = self.fastled_src / "platforms" / "wasm" / "compiler"

        if not arduino_src.exists():
            print(f"⚠️  Arduino compatibility headers not found at {arduino_src}")
            return []

        arduino_output = self.output_dir / "arduino"
        copied_files = []

        # Find header files (and optionally source files) in Arduino compatibility directory
        extensions = self.HEADER_EXTENSIONS.copy()
        if self.include_source:
            extensions.extend(self.SOURCE_EXTENSIONS)

        header_files = self._find_files_in_directory(arduino_src, extensions)
        print(f"   Found {len(header_files)} Arduino compatibility files")

        for header_file in header_files:
            # Copy directly to arduino output directory
            dest_path = arduino_output / header_file.name
            shutil.copy2(header_file, dest_path)
            copied_files.append(str(dest_path.relative_to(self.output_dir)))

        print(f"   Copied {len(copied_files)} Arduino files")
        return copied_files

    def _find_files_in_directory(
        self, directory: Path, extensions: List[str]
    ) -> List[Path]:
        """Find all files with specified extensions in a directory recursively.

        Args:
            directory: Directory to search
            extensions: List of file extensions to include (e.g., ['.h', '.cpp'])

        Returns:
            List of file paths
        """
        files = []

        if not directory.exists():
            return files

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                # Skip excluded patterns
                if not self._should_exclude_file(file_path):
                    files.append(file_path)

        return files

    def _find_headers_in_directory(self, directory: Path) -> List[Path]:
        """Find all header files in a directory recursively.

        Args:
            directory: Directory to search

        Returns:
            List of header file paths
        """
        return self._find_files_in_directory(directory, self.HEADER_EXTENSIONS)

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if a file should be excluded based on exclude patterns.

        Args:
            file_path: File to check

        Returns:
            True if file should be excluded
        """
        # Check against exclude patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if file_path.match(pattern):
                return True

        # Additional FastLED platform filtering (similar to sync.py)
        if "platforms" in file_path.parts:
            return not self._is_allowed_platform_path(file_path)

        return False

    def _is_platform_header(self, rel_path: Path) -> bool:
        """Check if a header is in a platform directory.

        Args:
            rel_path: Relative path within FastLED source

        Returns:
            True if this is a platform-specific header
        """
        return len(rel_path.parts) > 0 and rel_path.parts[0] == "platforms"

    def _is_allowed_platform_path(self, file_path: Path) -> bool:
        """Check if a platform path should be included (following sync.py logic).

        Args:
            file_path: File path to check

        Returns:
            True if the platform path should be included
        """
        parts = file_path.parts

        # Find platforms directory in path
        platform_idx = None
        for i, part in enumerate(parts):
            if part == "platforms":
                platform_idx = i
                break

        if platform_idx is None:
            return True  # Not in platforms directory

        # If directly in platforms/ (not in subdirectory), include it
        if platform_idx + 2 >= len(parts):  # platforms/filename
            return True

        # If in allowed subdirectories, include it
        if platform_idx + 1 < len(parts):
            platform_subdir = parts[platform_idx + 1]
            return platform_subdir in ["shared", "wasm", "stub", "posix"]

        return False

    def _write_manifest(self, manifest: Dict) -> None:
        """Write the manifest file.

        Args:
            manifest: Manifest data to write
        """
        manifest_path = self.output_dir / "manifest.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

        print(f"📄 Manifest written to: {manifest_path}")

    def _create_zip_archive(self, source_dir: Path, zip_path: Path) -> None:
        """Create a zip archive from the source directory.

        Args:
            source_dir: Directory containing headers to archive
            zip_path: Path where the zip file should be created
        """
        print(f"📦 Creating zip archive: {zip_path}")

        # Ensure parent directory exists
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zipf:
            # Walk through all files in the source directory
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path within the archive
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

        # Get zip file size for reporting
        zip_size = zip_path.stat().st_size
        if zip_size > 1024 * 1024:
            size_str = f"{zip_size / (1024 * 1024):.1f} MB"
        elif zip_size > 1024:
            size_str = f"{zip_size / 1024:.1f} KB"
        else:
            size_str = f"{zip_size} bytes"

        print(f"📦 Zip archive created: {zip_path} ({size_str})")


def dump_headers(
    output_dir: Path,
    include_source: bool = False,
) -> Dict[str, Any]:
    """Convenience function to dump headers.

    Args:
        output_dir: Directory where headers will be dumped
        include_source: Whether to include source files in addition to headers

    Returns:
        Dictionary with header categories and lists of relative file paths
    """
    dumper = HeaderDumper(output_dir, include_source)
    return dumper.dump_all_headers()


def dump_headers_to_zip(
    zip_path: Path,
    include_source: bool = False,
) -> Dict[str, Any]:
    """Programmatic function to dump headers to a zip file.

    This function always creates a zip archive at the specified path,
    regardless of the file extension provided by the caller.

    Args:
        zip_path: Path where the zip file will be created (extension will be enforced as .zip)
        include_source: Whether to include source files in addition to headers

    Returns:
        Dictionary with header categories and lists of relative file paths

    Example:
        >>> import tempfile
        >>> from pathlib import Path
        >>> temp_dir = Path(tempfile.mkdtemp())
        >>> zip_file = temp_dir / "my_headers.zip"
        >>> manifest = dump_headers_to_zip(zip_file, include_source=True)
        >>> print(f"Created zip with {manifest['metadata']['total_files']} files")
    """
    # Ensure the path has a .zip extension
    if not str(zip_path).lower().endswith(".zip"):
        zip_path = zip_path.with_suffix(".zip")

    dumper = HeaderDumper(zip_path, include_source)
    return dumper.dump_all_headers()
