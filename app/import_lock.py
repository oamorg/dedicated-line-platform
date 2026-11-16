"""Single-host import exclusion across API workers and CLI processes (Linux/macOS)."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

DEFAULT_LOCK = Path(__file__).resolve().parents[1] / "logs" / "imports" / ".import.lock"


class ImportBusy(RuntimeError):
    pass


@contextmanager
def import_lock(path=None, inherit=False):
    path = Path(path or os.getenv("IMPORT_LOCK_FILE", str(DEFAULT_LOCK))).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    inherited = os.environ.pop("DEDICATED_IMPORT_LOCK_FD", None) if inherit else None
    fd = int(inherited) if inherited is not None else os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if inherited is not None:
            actual, expected = os.fstat(fd), path.stat()
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise RuntimeError("Inherited import lock does not match the configured lock file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ImportBusy("An import process is already running") from exc
        yield fd
    finally:
        # Do not LOCK_UN: the child inherits this open file description and keeps the lock.
        os.close(fd)
