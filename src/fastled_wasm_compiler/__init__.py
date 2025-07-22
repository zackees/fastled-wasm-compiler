from pathlib import Path

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.compiler import UpdateSrcResult
from fastled_wasm_compiler.dump_headers import dump_headers_to_zip


class Compiler:
    """Forwarding class that delegates all calls to CompilerImpl."""

    def __init__(
        self, volume_mapped_src: Path | None = None, build_libs: list[str] | None = None
    ) -> None:
        from fastled_wasm_compiler.compiler import CompilerImpl

        self._impl = CompilerImpl(volume_mapped_src, build_libs)

    def compile(self, args: Args) -> Exception | None:
        return self._impl.compile(args)

    def update_src(
        self, builds: list[str] | None = None, src_to_merge_from: Path | None = None
    ) -> UpdateSrcResult | Exception:
        return self._impl.update_src(builds, src_to_merge_from)


class CompilerNative:
    """Forwarding class that delegates all calls to NativeCompilerImpl."""

    def __init__(self, emsdk_install_dir: Path | None = None) -> None:
        from fastled_wasm_compiler.compile_sketch_native import NativeCompilerImpl

        self._impl = NativeCompilerImpl(emsdk_install_dir)

    def ensure_emsdk(self) -> None:
        return self._impl.ensure_emsdk()

    def get_compilation_env(self) -> dict[str, str]:
        return self._impl.get_compilation_env()

    def get_tool_paths(self) -> dict[str, Path]:
        return self._impl.get_tool_paths()

    def compile_source_to_object(
        self, source_file: Path, build_mode: str, build_dir: Path
    ) -> Path:
        return self._impl.compile_source_to_object(source_file, build_mode, build_dir)

    def link_objects_to_wasm(
        self,
        object_files: list[Path],
        build_mode: str,
        output_dir: Path,
        fastled_lib_path: Path | None = None,
        output_name: str = "fastled",
    ) -> Path:
        return self._impl.link_objects_to_wasm(
            object_files, build_mode, output_dir, fastled_lib_path, output_name
        )

    def compile_sketch(
        self, sketch_dir: Path, build_mode: str, output_dir: Path | None = None
    ) -> Path:
        return self._impl.compile_sketch(sketch_dir, build_mode, output_dir)


__all__ = [
    "Compiler",
    "CompilerNative",
    "dump_headers_to_zip",
]
