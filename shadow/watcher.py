from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .capture import CaptureBundle, bundle_filenames, write_bundle


class PendingReplacer(FileSystemEventHandler):
    """Delete observer writes and replace them with the frozen capture set."""

    def __init__(self, pending_dir: Path, bundle: CaptureBundle) -> None:
        super().__init__()
        self.pending_dir = pending_dir
        self.bundle = bundle
        self._lock = threading.RLock()
        self._owned: set[str] = set()
        self._pending_flush: set[str] = set()
        self._timer: threading.Timer | None = None
        self._next_ts = bundle.captured_at + timedelta(seconds=1)
        self._observer: Observer | None = None
        self._running = False

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            # Seed the frozen set once at disable time.
            self._write_owned(self.bundle.captured_at)
            self._observer = Observer()
            self._observer.schedule(self, str(self.pending_dir), recursive=False)
            self._observer.start()
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=3)
                self._observer = None
            self._owned.clear()
            self._pending_flush.clear()

    @property
    def running(self) -> bool:
        return self._running

    def on_created(self, event: FileSystemEvent) -> None:
        self._on_event(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._on_event(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._on_event(event)

    def _on_event(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        path = Path(str(getattr(event, "dest_path", None) or event.src_path))
        try:
            if path.parent.resolve() != self.pending_dir.resolve():
                return
        except OSError:
            if path.parent != self.pending_dir:
                return
        name = path.name
        with self._lock:
            if not self._running:
                return
            if name in self._owned:
                return
            self._pending_flush.add(name)
            if self._timer is not None:
                self._timer.cancel()
            # Debounce so jpg + sidecars settle before we replace the batch.
            self._timer = threading.Timer(0.35, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            if not self._running:
                return
            names = list(self._pending_flush)
            self._pending_flush.clear()
            self._timer = None

        # Delete foreign files that appeared.
        for name in names:
            if name in self._owned:
                continue
            target = self.pending_dir / name
            self._safe_unlink(target)
            # Observer often writes jpg then sidecars with the same stem.
            if name.endswith(".jpg"):
                for suffix in (".caption", ".clicks", ".keyboards"):
                    self._safe_unlink(self.pending_dir / f"{name}{suffix}")

        # Replace with frozen capture under a growing timestamp.
        with self._lock:
            if not self._running:
                return
            # Advance at least 1s; prefer wall clock so stamps look natural.
            now = datetime.now()
            if now <= self._next_ts:
                ts = self._next_ts
            else:
                ts = now
            self._next_ts = ts + timedelta(seconds=1)
            self._write_owned(ts)

    def _write_owned(self, ts: datetime) -> None:
        # Mark names owned before writing so watchdog events ignore our own files.
        names = bundle_filenames(ts, self.bundle.activity)
        self._owned = set(names)
        write_bundle(self.pending_dir, self.bundle, ts=ts)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        for _ in range(8):
            try:
                if path.exists():
                    path.unlink()
                return
            except OSError:
                time.sleep(0.05)
