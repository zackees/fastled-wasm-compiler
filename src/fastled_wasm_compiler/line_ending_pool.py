"""
Line ending conversion process pool for parallel file processing.

This module provides a queue-based multiprocessing system for converting line endings
and copying files with proper handling of text/binary files and graceful shutdown.
"""

import _thread
import atexit
import logging
import multiprocessing as mp
import threading
import uuid
from concurrent.futures import Future
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Create logger for this module
logger: logging.Logger = logging.getLogger(__name__)


def _line_ending_worker(src_path_str: str, dst_path_str: str) -> Union[bool, Exception]:
    """Worker function for converting line endings and copying files.

    Reads source file, converts line endings, compares with destination, and writes if different.

    Args:
        src_path_str: String path to the source file
        dst_path_str: String path to the destination file

    Returns:
        bool: True if files were different and update was applied, False if files were same
        Exception: If an error occurred during processing
    """
    try:
        src_path: Path = Path(src_path_str)
        dst_path: Path = Path(dst_path_str)

        # Check if source file exists
        if not src_path.exists():
            return FileNotFoundError(f"Source file does not exist: {src_path}")

        # Check if source file is readable
        if not src_path.is_file():
            return OSError(f"Source path is not a file: {src_path}")

        # Read source file with better error handling
        try:
            src_bytes: bytes = src_path.read_bytes()
        except FileNotFoundError:
            return FileNotFoundError(
                f"Source file was deleted during processing: {src_path}"
            )
        except PermissionError as e:
            return PermissionError(
                f"Permission denied reading source file {src_path}: {e}"
            )
        except OSError as e:
            return OSError(f"Error reading source file {src_path}: {e}")

        # Improved binary file detection
        def is_binary(data: bytes) -> bool:
            """Check if data is binary by looking for null bytes and control characters."""
            if b"\x00" in data:
                return True
            # Check for high ratio of control characters (excluding common ones like \r, \n, \t)
            if len(data) > 0:
                control_chars: int = sum(
                    1 for b in data if b < 32 and b not in (9, 10, 13)
                )
                return control_chars / len(data) > 0.1
            return False

        # Try to decode as text, but use better binary detection
        src_text: Optional[str] = None
        is_text_file: bool = True

        if is_binary(src_bytes):
            is_text_file = False
        else:
            try:
                src_text = src_bytes.decode("utf-8")
            except UnicodeDecodeError:
                is_text_file = False

        # Convert line endings if it's a text file
        if is_text_file and src_text is not None:
            converted_text: str = src_text.replace("\r\n", "\n")
            final_bytes: bytes = converted_text.encode("utf-8")
        else:
            final_bytes = src_bytes

        # Check if destination exists and compare (with error handling)
        dst_exists: bool = False
        dst_bytes: Optional[bytes] = None
        try:
            if dst_path.exists() and dst_path.is_file():
                dst_exists = True
                dst_bytes = dst_path.read_bytes()
        except (FileNotFoundError, PermissionError):
            # Destination was deleted or not accessible - treat as not existing
            dst_exists = False
        except OSError as e:
            return OSError(f"Error reading destination file {dst_path}: {e}")

        # Compare content if destination exists
        if dst_exists and dst_bytes is not None:
            if final_bytes == dst_bytes:
                return False  # Files are the same, no update needed

        # Files are different or destination doesn't exist - write the file
        try:
            # Ensure parent directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file atomically by writing to a temp file first
            temp_path: Path = dst_path.with_suffix(dst_path.suffix + ".tmp")
            try:
                temp_path.write_bytes(final_bytes)
                # Atomic move (on most filesystems)
                temp_path.replace(dst_path)
            except Exception as e:
                # Clean up temp file if it exists
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass  # Ignore cleanup errors
                raise e

        except PermissionError as e:
            return PermissionError(
                f"Permission denied writing to destination {dst_path}: {e}"
            )
        except OSError as e:
            return OSError(f"Error writing to destination file {dst_path}: {e}")

        return True  # Update was applied

    except Exception as e:
        # Catch any unexpected errors
        return Exception(
            f"Unexpected error processing {src_path_str} -> {dst_path_str}: {e}"
        )


def _queue_worker(
    input_queue: "mp.Queue[Optional[Tuple[str, str, str]]]",
    output_queue: "mp.Queue[Tuple[str, Union[bool, Exception]]]",
) -> None:
    """Queue-based worker process for line ending conversion."""
    while True:
        task_id: str = "unknown"  # Initialize to prevent unbound variable error
        try:
            item: Optional[Tuple[str, str, str]] = input_queue.get()
            if item is None:  # Shutdown signal
                break

            src_path_str: str
            dst_path_str: str
            task_id, src_path_str, dst_path_str = item
            result: Union[bool, Exception] = _line_ending_worker(
                src_path_str, dst_path_str
            )
            output_queue.put((task_id, result))

        except KeyboardInterrupt:
            # Gracefully exit on KeyboardInterrupt
            logger.debug("Worker process received KeyboardInterrupt, shutting down")
            break
        except Exception as e:
            # If we can't get task_id, use a placeholder
            try:
                output_queue.put((task_id, e))
            except (NameError, Exception):
                output_queue.put(("unknown", e))


class LineEndingProcessPool:
    """Queue-based process pool for parallel line ending conversion."""

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self.max_workers: int = max_workers or min(8, (mp.cpu_count() or 1) + 4)
        self.pending_tasks: Dict[str, Future[Union[bool, Exception]]] = (
            {}
        )  # task_id -> Future
        self._shutdown_event: threading.Event = threading.Event()

        # Initialize workers immediately in constructor
        logger.debug(
            f"Initializing line ending queue workers with {self.max_workers} workers"
        )
        self.input_queue: "mp.Queue[Optional[Tuple[str, str, str]]]" = mp.Queue()
        self.output_queue: "mp.Queue[Tuple[str, Union[bool, Exception]]]" = mp.Queue()

        # Start daemon worker processes
        self.workers: List[mp.Process] = []
        for i in range(self.max_workers):
            worker: mp.Process = mp.Process(
                target=_queue_worker,
                args=(self.input_queue, self.output_queue),
                daemon=True,  # Daemon processes don't block shutdown
            )
            worker.start()
            self.workers.append(worker)

        # Start result collector thread
        self._start_result_collector()

    def _start_result_collector(self) -> None:
        """Start background thread to collect results from output queue."""

        def _collect_results() -> None:
            while not self._shutdown_event.is_set():
                try:
                    task_id: str
                    result: Union[bool, Exception]
                    task_id, result = self.output_queue.get(timeout=1.0)

                    # Find the corresponding future and set result
                    future: Optional[Future[Union[bool, Exception]]] = (
                        self.pending_tasks.pop(task_id, None)
                    )
                    if future is not None:
                        future.set_result(result)

                except KeyboardInterrupt:
                    # Propagate KeyboardInterrupt to main thread
                    logger.debug("Result collector received KeyboardInterrupt")
                    _thread.interrupt_main()
                    break
                except Exception:
                    # Timeout or other error - continue if not shutting down
                    if self._shutdown_event.is_set():
                        break

        collector_thread: threading.Thread = threading.Thread(
            target=_collect_results, daemon=True
        )
        collector_thread.start()

    def convert_file_line_endings_async(
        self, src_path: Path, dst_path: Path
    ) -> Future[Union[bool, Exception]]:
        """Submit file line ending conversion to the queue (non-blocking)."""
        if self._shutdown_event.is_set():
            raise RuntimeError("Process pool is shutting down")

        # Generate unique task ID
        task_id: str = str(uuid.uuid4())

        # Create future for this task
        future: Future[Union[bool, Exception]] = Future()
        self.pending_tasks[task_id] = future

        # Submit task to input queue
        self.input_queue.put((task_id, str(src_path), str(dst_path)))

        return future

    def convert_file_line_endings(
        self, src_path: Path, dst_path: Path
    ) -> Union[bool, Exception]:
        """Submit file line ending conversion to the queue (blocking)."""
        async_result: Future[Union[bool, Exception]] = (
            self.convert_file_line_endings_async(src_path, dst_path)
        )
        return async_result.result()

    def shutdown(self) -> None:
        """Shutdown the worker processes."""
        logger.debug("Shutting down line ending queue workers")
        self._shutdown_event.set()

        # Send shutdown signals to all workers
        for _ in range(self.max_workers):
            try:
                self.input_queue.put(None)
            except (OSError, ValueError):
                pass  # Queue might be closed

        # Wait for workers to finish (with timeout since they're daemon)
        for worker in self.workers:
            worker.join(timeout=1.0)

        # Cancel any remaining pending tasks
        for task_id, future in self.pending_tasks.items():
            if not future.done():
                future.cancel()

        # Clean up
        self.workers.clear()
        self.pending_tasks.clear()


# Global process pool instance with lazy initialization
_global_line_ending_pool: Optional[LineEndingProcessPool] = None
_pool_creation_lock: threading.Lock = threading.Lock()


def get_line_ending_pool() -> LineEndingProcessPool:
    """Get the global line ending process pool, creating it lazily on first use.

    Uses double-checked locking pattern to ensure thread-safe lazy initialization.
    This prevents process pool creation in server environments where it may not be needed.
    """
    global _global_line_ending_pool

    # First check without lock (fast path for already-created pool)
    if _global_line_ending_pool is not None:
        return _global_line_ending_pool

    # Use lock for thread-safe creation
    with _pool_creation_lock:
        # Double-check pattern: another thread might have created it while we waited
        if _global_line_ending_pool is None:
            logger.debug("Creating global line ending process pool on first use")
            _global_line_ending_pool = LineEndingProcessPool()

        return _global_line_ending_pool


def shutdown_global_pool() -> None:
    """Shutdown the global line ending process pool."""
    global _global_line_ending_pool

    with _pool_creation_lock:
        if _global_line_ending_pool is not None:
            logger.debug("Shutting down global line ending process pool")
            _global_line_ending_pool.shutdown()
            _global_line_ending_pool = None


# Register cleanup on exit
atexit.register(shutdown_global_pool)
