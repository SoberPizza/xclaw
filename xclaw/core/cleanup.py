"""Artifact retention — delete oldest files when count exceeds limit."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def enforce_max_files(directory: Path, pattern: str, max_count: int) -> None:
    """Keep at most *max_count* files matching *pattern* in *directory*.

    Files are sorted by modification time; the oldest ones beyond the
    limit are deleted.  Errors on individual deletions are logged but
    never propagated.
    """
    if max_count <= 0:
        return
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    excess = len(files) - max_count
    if excess <= 0:
        return
    for f in files[:excess]:
        try:
            f.unlink()
        except OSError as e:
            logger.warning("Failed to remove old artifact %s: %s", f, e)
