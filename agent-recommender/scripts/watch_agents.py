"""Auto-index watcher — rebuild the Chroma store whenever agents/ changes.

Watches ``config.AGENTS_DIR`` for `.md` files being added, modified, or deleted
and, on each change, rebuilds the index and refreshes the catalog caches so a
running app/server picks up the change immediately (no restart). This pairs with
the cache-invalidation work in ``store.refresh_catalog_caches`` — adding a new
agent `.md` becomes a zero-touch operation while this watcher runs.

Manual, long-running tool (not used by the test suite):

    pip install watchdog          # if not already installed
    python scripts/watch_agents.py

Press Ctrl-C to stop.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

# Make `import src` work regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

from src import build_index, config  # noqa: E402
from src.store import refresh_catalog_caches  # noqa: E402

_RELEVANT_EVENTS = {"created", "modified", "deleted", "moved"}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _reindex(reason: str) -> None:
    """Rebuild the store and refresh caches, with timestamped logging."""
    print(f"[{_stamp()}] {reason} -> re-indexing…", flush=True)
    try:
        stats = build_index()
        # build_index() already refreshes caches; call again explicitly so this
        # holds even if that internal call is ever removed.
        refresh_catalog_caches()
    except Exception as exc:  # keep the watcher alive on a transient failure
        print(f"[{_stamp()}] re-index FAILED: {exc!r}", flush=True)
        return
    print(
        f"[{_stamp()}] re-indexed {stats['agents']} agents "
        f"({stats['summary_records']} summary + {stats['section_records']} section records).",
        flush=True,
    )


def _is_md(path: str) -> bool:
    return str(path).lower().endswith(".md")


class _MarkdownHandler(FileSystemEventHandler):
    """Re-index on any create / modify / delete / move of a `.md` file."""

    def on_any_event(self, event) -> None:
        if event.is_directory or event.event_type not in _RELEVANT_EVENTS:
            return
        src_path = getattr(event, "src_path", "") or ""
        dest_path = getattr(event, "dest_path", "") or ""
        if not (_is_md(src_path) or _is_md(dest_path)):
            return
        changed = Path(dest_path or src_path).name
        _reindex(f"{event.event_type} {changed}")


def main() -> int:
    agents_dir = Path(config.AGENTS_DIR)
    print(f"[{_stamp()}] watching {agents_dir} for .md changes (Ctrl-C to stop)…", flush=True)

    # Build once up front so the store reflects the current catalog on startup.
    _reindex("initial build")

    observer = Observer()
    observer.schedule(_MarkdownHandler(), str(agents_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(f"\n[{_stamp()}] stopped.", flush=True)
    observer.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
