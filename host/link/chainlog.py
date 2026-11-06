"""A log whose entries are chained by hash: each entry carries the hash of the one before, so a change, a deletion or a reordering
of any past entry is detected by `verify`. Plain JSON lines, readable by anyone.

This protects against accidents and casual edits. It is not a signature: someone who can rewrite the whole file can recompute
the chain, so keep a copy of the last hash somewhere else when it matters.
"""
import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _digest(previous, body):
    return hashlib.sha256((previous + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode("utf-8")).hexdigest()


class ChainLog:
    def __init__(self, path):
        self.path = Path(path)
        self.last = GENESIS
        self.count = 0
        if self.path.exists():
            ok, count, last = self.verify(self.path)
            if not ok:
                raise ValueError(f"{self.path} does not verify: the chain breaks at entry {count + 1}")
            self.count, self.last = count, last

    def append(self, **entry):
        """Adds an entry (any JSON-serialisable fields) and returns its hash."""
        body = {"n": self.count + 1, **entry}
        digest = _digest(self.last, body)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"body": body, "prev": self.last, "hash": digest}, sort_keys=True) + "\n")
        self.count += 1
        self.last = digest
        return digest

    @staticmethod
    def verify(path):
        """Returns (ok, entries_verified, last_hash). On a failure, entries_verified is the number of good entries before it."""
        previous, count = GENESIS, 0
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                body, prev, digest = record["body"], record["prev"], record["hash"]
            except (ValueError, KeyError, TypeError):
                return False, count, previous
            if prev != previous or digest != _digest(previous, body) or body.get("n") != count + 1:
                return False, count, previous
            previous, count = digest, count + 1
        return True, count, previous
