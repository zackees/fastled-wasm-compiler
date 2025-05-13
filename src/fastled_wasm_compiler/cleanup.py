import shutil
from pathlib import Path

from fastled_wasm_compiler.args import Args


def cleanup(args: Args, js_src: Path) -> None:
    if not args.keep_files and not (args.only_copy or args.only_insert_header):
        print("Removing temporary source files")
        shutil.rmtree(js_src)
    else:
        print("Keeping temporary source files")
