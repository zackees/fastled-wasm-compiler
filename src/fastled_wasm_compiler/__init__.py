from pathlib import Path
from typing import Dict, List, Optional

from fastled_wasm_compiler.compiler import UpdateSrcResult


class Compiler:
    """Forwarding class that delegates all calls to CompilerImpl."""

    def __init__(
        self, volume_mapped_src: Path | None = None, build_libs: list[str] | None = None
    ) -> None:
        from fastled_wasm_compiler.compiler import CompilerImpl

        self._impl = CompilerImpl(volume_mapped_src, build_libs)

    def compile(self, args) -> Exception | None:
        return self._impl.compile(args)

    def update_src(
        self, builds: list[str] | None = None, src_to_merge_from: Path | None = None
    ) -> UpdateSrcResult | Exception:
        return self._impl.update_src(builds, src_to_merge_from)


class CompilerNative:
    """Forwarding class that delegates all calls to NativeCompilerImpl."""

    def __init__(self, emsdk_install_dir: Optional[Path] = None):
        from fastled_wasm_compiler.compile_sketch_native import NativeCompilerImpl

        self._impl = NativeCompilerImpl(emsdk_install_dir)

    def ensure_emsdk(self) -> None:
        return self._impl.ensure_emsdk()

    def get_compilation_env(self) -> Dict[str, str]:
        return self._impl.get_compilation_env()

    def get_tool_paths(self) -> Dict[str, Path]:
        return self._impl.get_tool_paths()

    def compile_source_to_object(
        self, source_file: Path, build_mode: str, build_dir: Path
    ) -> Path:
        return self._impl.compile_source_to_object(source_file, build_mode, build_dir)

    def link_objects_to_wasm(
        self,
        object_files: List[Path],
        build_mode: str,
        output_dir: Path,
        output_name: str = "fastled",
    ) -> Path:
        return self._impl.link_objects_to_wasm(
            object_files, build_mode, output_dir, output_name
        )

    def compile_sketch(
        self, sketch_dir: Path, build_mode: str, output_dir: Optional[Path] = None
    ) -> Path:
        return self._impl.compile_sketch(sketch_dir, build_mode, output_dir)


__all__ = [
    "Compiler",
    "CompilerNative",
]
