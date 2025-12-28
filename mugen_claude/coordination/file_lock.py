"""
File locking utilities for coordinating file access between agents.
"""
import os
import fcntl
import time
from typing import Optional
from contextlib import contextmanager


class FileLock:
    """
    OS-level file locking using fcntl (Unix/macOS) or msvcrt (Windows).
    Provides exclusive access to files across processes.
    """

    def __init__(self, file_path: str, timeout: float = 10.0):
        """
        Initialize file lock.

        Args:
            file_path: Path to the file to lock
            timeout: Maximum time to wait for lock acquisition (seconds)
        """
        self.file_path = file_path
        self.timeout = timeout
        self.lock_file_path = f"{file_path}.lock"
        self.lock_fd = None

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the file lock.

        Args:
            blocking: If True, wait up to timeout for lock. If False, return immediately.

        Returns:
            True if lock acquired, False otherwise
        """
        if self.lock_fd is not None:
            # Already have the lock
            return True

        # Create lock file if it doesn't exist
        self.lock_fd = open(self.lock_file_path, 'w')

        if blocking:
            # Try to acquire with timeout
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except BlockingIOError:
                    if time.time() - start_time > self.timeout:
                        self.lock_fd.close()
                        self.lock_fd = None
                        return False
                    time.sleep(0.1)
        else:
            # Non-blocking
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                self.lock_fd.close()
                self.lock_fd = None
                return False

    def release(self):
        """Release the file lock."""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
            finally:
                self.lock_fd = None
                # Clean up lock file
                try:
                    os.remove(self.lock_file_path)
                except OSError:
                    pass

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock for {self.file_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()

    def __del__(self):
        """Ensure lock is released on deletion."""
        self.release()


@contextmanager
def file_lock(file_path: str, timeout: float = 10.0):
    """
    Context manager for file locking.

    Usage:
        with file_lock('/path/to/file.txt'):
            # Exclusive access to file
            with open('/path/to/file.txt', 'w') as f:
                f.write('data')
    """
    lock = FileLock(file_path, timeout)
    try:
        if not lock.acquire():
            raise TimeoutError(f"Could not acquire lock for {file_path}")
        yield lock
    finally:
        lock.release()
