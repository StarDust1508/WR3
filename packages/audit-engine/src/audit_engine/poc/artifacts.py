"""PoC artifact storage.

For MVP we write to a directory tree on the local filesystem. Later weeks
(W12+) upload to Cloudflare R2 with the same interface — see TZ.md section 5.3.
Caller holds a PoCArtifactStore and asks for paths.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitize(part: str, *, max_len: int = 64) -> str:
    cleaned = _SAFE_ID.sub("_", part)
    if len(cleaned) > max_len:
        # Keep a stable suffix from a hash so collisions are unlikely.
        suffix = hashlib.sha1(part.encode()).hexdigest()[:8]
        cleaned = cleaned[: max_len - 9] + "_" + suffix
    return cleaned or "x"


class PoCArtifactStore:
    """Local-fs storage of PoC tests + run logs, keyed by scan + finding id."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.getenv("WR3_POC_ROOT") or "poc-output").resolve()

    def workspace_for(self, *, scan_id: str, finding_id: str) -> Path:
        """Return a unique workspace dir for the given scan+finding pair."""
        d = self.root / _sanitize(scan_id) / _sanitize(finding_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_test(self, *, workspace: Path, content: str, attempt: int) -> Path:
        """Save the Solidity test source for one retry attempt. Returns its path."""
        path = workspace / f"PoC.attempt{attempt}.t.sol"
        path.write_text(content, encoding="utf-8")
        return path

    def save_log(self, *, workspace: Path, attempt: int, body: str) -> Path:
        path = workspace / f"forge.attempt{attempt}.log"
        path.write_text(body, encoding="utf-8")
        return path

    def relative(self, path: Path) -> str:
        """Path relative to artifact root, for storing in DB."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)
