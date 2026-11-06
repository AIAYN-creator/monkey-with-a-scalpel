"""The library: where the model keeps what it reads. It can fetch any document (a paper, a datasheet, a page) and read it again later;
there is no quota, no list of allowed sources and no size limit here. Every fetch goes to the hash-chained log with the address, the size
and the hash of the content, so a person can see exactly what the model read and what a proposal cites.

Network access is a function you give it (`fetcher(source) -> bytes`), so the tests run offline and the real client is a few lines.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Document:
    id: str  # first 16 hex of the content hash: the same content is the same document
    source: str
    size: int


class Library:
    def __init__(self, folder, fetcher, log=None):
        self.folder, self.fetcher, self.log = Path(folder), fetcher, log
        self.folder.mkdir(parents=True, exist_ok=True)
        self.documents = {}

    def fetch(self, source):
        """Gets a document from an address or a path and stores it. Never refuses a source."""
        content = self.fetcher(source)
        if isinstance(content, str):
            content = content.encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        doc = Document(digest[:16], source, len(content))
        (self.folder / doc.id).write_bytes(content)
        self.documents[doc.id] = doc
        if self.log is not None:
            self.log.append(event="document_fetched", id=doc.id, source=source, size=doc.size, sha256=digest)
        return doc

    def read(self, doc_id):
        if doc_id not in self.documents:
            raise KeyError(f"no document {doc_id!r} in the library")
        return (self.folder / doc_id).read_bytes()

    def text(self, doc_id):
        return self.read(doc_id).decode("utf-8", errors="replace")
