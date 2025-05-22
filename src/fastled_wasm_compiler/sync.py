import fnmatch
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Create logger for this module
logger = logging.getLogger(__name__)

_LOGGING_ENABLED = False

# Create formatter with filename and line number
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Set logger level based on _LOGGING_ENABLED flag
if not _LOGGING_ENABLED:
    logger.setLevel(logging.CRITICAL)  # Effectively disables most logging
else:
    logger.setLevel(logging.INFO)


class FilterType(Enum):
    """Enum to represent filter type."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass
class FilterOp:
    """Class to hold include filter information."""

    filter: FilterType
    glob: list[str]

    def __post_init__(self) -> None:
        if self.filter == FilterType.EXCLUDE and not self.glob:
            raise ValueError("Exclude filter must have a glob pattern")

    def matches(self, path: Path) -> bool:
        """Check if the path matches the filter."""
        # assert path.is_file(), f"Path {path} is not a file"
        # Check if the path matches the glob pattern
        path_str = path.as_posix()
        if not path_str.startswith("/"):
            if not path_str.startswith("./") and path_str != path.absolute().as_posix():
                path_str = "./" + path_str
        # return any(prefixed_path.match(g) for g in self.glob)
        for g in self.glob:
            if fnmatch.fnmatch(path_str, g):
                return True
        return False


@dataclass
class FilterList:
    """Class to hold filter information."""

    file_glob: list[str]
    filter_list: list[FilterOp]

    def _passes(self, path: Path) -> bool:
        """Check if a path passes the filter."""
        # assert path.is_file(), f"Path {path} is not a file"
        # firsts check that the file glob passes
        if self.file_glob:
            if not any(path.match(g) for g in self.file_glob):
                return False
        # Next, march through the filter list
        if not self.filter_list:
            return True
        for filter_op in self.filter_list:
            # first filter wins
            match = filter_op.matches(path)
            if match:
                if filter_op.filter == FilterType.INCLUDE:
                    return True
                else:
                    return False
        # If we get here, we didn't match any filters
        return True

    def passes(self, path: Path) -> bool:
        out = self._passes(path)
        return out


_FILTER_SRC = FilterList(
    # Exclude "platforms/"
    file_glob=[],
    filter_list=[
        FilterOp(filter=FilterType.EXCLUDE, glob=["**/platforms/**"]),
    ],
)

_FILTER_INCLUDE_ALL = FilterList(
    file_glob=[],
    filter_list=[],
)

_FILTER_INCLUDE_ONLY_ROOT_FILES = FilterList(
    file_glob=[],
    filter_list=[
        FilterOp(filter=FilterType.EXCLUDE, glob=["**/platforms/**/**"]),
        FilterOp(filter=FilterType.INCLUDE, glob=["**/platforms/*.*"]),
    ],
)


_FILTER_EXAMPLES = FilterList(
    file_glob=[],
    filter_list=[
        FilterOp(filter=FilterType.EXCLUDE, glob=["**/fastled_js/**"]),
    ],
)


def _task_copy(src: Path, dst: Path, dryrun: bool) -> Path | None:
    if not dst.exists():
        # logger.info(f"Copying new file {src} to {dst}")
        file_src_bytes = src.read_bytes()
        file_src_bytes = file_src_bytes.replace(b"\r\n", b"\n")
        if not dryrun:
            # file_dst.write_bytes(file_src_bytes)
            # open and write
            print(f"Copying new file {src} to {dst}")
            with open(dst, "wb") as f:
                f.write(file_src_bytes)
        return dst
    else:
        logger.info(f"File {dst} already exists")
        # File already exists, but are the bytes the sames?
        file_src_bytes = src.read_bytes()
        file_dst_bytes = dst.read_bytes()
        # normalize line endings to \n
        file_src_bytes = file_src_bytes.replace(b"\r\n", b"\n")
        # source code is already guaranteed to have normalized line endings.
        # file_dst_bytes = file_dst_bytes.replace(b"\r\n", b"\n")
        if file_src_bytes == file_dst_bytes:
            logger.info(f"File {dst} already exists and is no different")
            return None
        # replace
        # overwrite the file
        logger.info(f"Overwriting {dst} with {src}")
        if not dryrun:
            print(f"Overwriting {dst} with {src} because bytes were different")
            dst.write_bytes(file_src_bytes)
        return dst


def _sync_subdir(
    src: Path, dst: Path, filter_list: FilterList, dryrun: bool
) -> list[Path]:
    """Return true when source files changed. At this point we always turn true
    TODO: Check if the file is newer than the destination file
    """
    logger.info(f"Syncing directories from {src} to {dst}")
    assert src.is_dir(), f"Source {src} is not a directory"
    # assert dst.is_dir(), f"Destination {dst} is not a directory"
    if not dst.exists():
        logger.info(f"Creating destination directory {dst}")
        dst.mkdir(parents=True, exist_ok=True)
    src_list: list[Path] = list(src.rglob("*"))
    dst_list: list[Path] = list(dst.rglob("*"))

    # filter out all directories
    src_list = [s for s in src_list if s.is_file()]
    dst_list = [d for d in dst_list if d.is_file()]

    # Filter the source list and dst list
    src_list = [s for s in src_list if filter_list.passes(s)]
    dst_list = [d for d in dst_list if filter_list.passes(d)]

    # set of relative paths
    src_set: set[Path] = {s.relative_to(src) for s in src_list}
    dst_set: set[Path] = {d.relative_to(dst) for d in dst_list}

    # create all dst directories that are missing.
    missing_parents_set: set[Path] = set()
    # Find all missing directories on dst
    for file in src_set:
        file_dst = dst / file
        if not file_dst.parent.exists():
            if file_dst.parent not in missing_parents_set:
                missing_parents_set.add(file_dst.parent)
    # Do it in one bulk creation.
    for dir in missing_parents_set:
        if not dryrun:
            dir.mkdir(parents=True, exist_ok=True)

    files_to_delete_on_dst: set[Path] = dst_set - src_set
    out_changed_files: list[Path] = []
    futures: list[Future] = []
    with ThreadPoolExecutor(max_workers=32) as executor:
        for file in src_set:
            file_src = src / file
            file_dst = dst / file
            logger.info(f"Copying {file_src} to {file_dst}")

            def _task_cpy(file_src=file_src, file_dst=file_dst) -> Path | None:
                return _task_copy(file_src, file_dst, dryrun=dryrun)

            future = executor.submit(_task_cpy)
            futures.append(future)

    exceptions = []

    for future in futures:
        try:
            result = future.result()
            if result is not None:
                out_changed_files.append(result)
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            exceptions.append(e)

    # Now do removal
    futures.clear()
    with ThreadPoolExecutor(max_workers=32) as executor:
        for file in files_to_delete_on_dst:
            file_dst = dst / file

            def task_remove_missing_from_dst(file_dst=file_dst) -> bool:
                if not dryrun:
                    assert file_dst.is_file(), f"File {file_dst} does not exist"
                    file_dst.unlink()
                return True

            future = executor.submit(task_remove_missing_from_dst)
            futures.append(future)

    out_changed_files += files_to_delete_on_dst

    for future in futures:
        try:
            future.result()
        except Exception as e:
            # logger.error(f"Error deleting file: {e}")
            # raise e
            exceptions.append(e)
    if exceptions:
        logger.error(f"Errors deleting files: {exceptions}")
        raise Exception(f"Errors deleting files: {exceptions}")

    logger.info(f"Syncing directories from {src} to {dst} complete")
    return out_changed_files


def _sync_fastled_examples(src: Path, dst: Path, dryrun: bool = False) -> list[Path]:
    if src.exists():
        changed = _sync_subdir(src, dst, _FILTER_EXAMPLES, dryrun)
        return changed
    return []


def _sync_fastled_src(src: Path, dst: Path, dryrun: bool = False) -> list[Path]:
    changed_src = _sync_subdir(src, dst, _FILTER_SRC, dryrun)
    changed_wasm = _sync_subdir(
        src / "platforms" / "wasm",
        dst / "platforms" / "wasm",
        _FILTER_INCLUDE_ALL,
        dryrun=dryrun,
    )
    changed_stub = _sync_subdir(
        src / "platforms" / "stub",
        dst / "platforms" / "stub",
        _FILTER_INCLUDE_ALL,
        dryrun=dryrun,
    )
    changed_platform_root_files = _sync_subdir(
        src / "platforms",
        dst / "platforms",
        _FILTER_INCLUDE_ONLY_ROOT_FILES,
        dryrun=dryrun,
    )
    if changed_src:
        print(f"Changed src files: {changed_src}")
    if changed_wasm:
        print(f"Changed wasm files: {changed_wasm}")
    if changed_stub:
        print(f"Changed stub files: {changed_stub}")
    if changed_platform_root_files:
        print(f"Changed platform root files: {changed_platform_root_files}")
    files_changed = (
        changed_src + changed_wasm + changed_stub + changed_platform_root_files
    )
    return files_changed


def sync_fastled(
    src: Path, dst: Path, dryrun: bool = False, sync_examples: bool = True
) -> list[Path]:
    """Sync the source directory to the destination directory."""
    start = time.time()
    # assert (src / "FastLED.h").exists(), f"Source {src} does not contain FastLED.h"
    logger.info(f"Syncing {src} to {dst}")
    if not dst.exists():
        logger.info(f"Creating destination directory {dst}")
        dst.mkdir(parents=True, exist_ok=True)
    changed = _sync_fastled_src(src, dst, dryrun=dryrun)

    if sync_examples:
        src_examples = src.parent / "examples"
        dst_examples = dst.parent / "examples"
        if src_examples.exists():
            _sync_fastled_examples(src_examples, dst_examples, dryrun=dryrun)
        else:
            src_examples = src / "examples"
            dst_examples = dst / "examples"
            if src_examples.exists():
                _sync_fastled_examples(src_examples, dst_examples, dryrun=dryrun)
            else:
                # examples_blink = src / "Blink"
                src_examples_blink = src / "Blink"
                dst_examples_blink = dst / "Blink"
                if src_examples_blink.exists():
                    _sync_fastled_examples(
                        src_examples_blink, dst_examples_blink, dryrun=dryrun
                    )
    print(
        f"Syncing (dryrun) from {src} to {dst} complete in {time.time() - start:.2f} seconds"
    )
    return changed
