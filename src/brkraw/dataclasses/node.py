from __future__ import annotations

import io
from typing import Any, List, Union, Optional, TYPE_CHECKING, cast, Dict


from ..core.fs import DatasetFS
from ..core.parameters import Parameters

if TYPE_CHECKING:
    from ..core.fs import DatasetFile
    from ..core.zip import ZippedFile

def _is_probably_text(data: bytes) -> bool:
    """Heuristic to decide if data should be treated as text."""
    if not data:
        return True
    sample = data[:1024]
    if b"\x00" in sample:
        return False

    text_chars = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D, 0x08, 0x0C, 0x1B}
    nontext = sum(b not in text_chars for b in sample)
    return (nontext / len(sample)) < 0.30


class DatasetNode:
    """Shared utilities for dataset-backed nodes (Study, Scan, Reco)."""

    fs: "DatasetFS"
    relroot: str
    _cache: Dict[str, Any]

    def _full_path(self, name: str) -> str:
        relroot = self.relroot.strip("/")
        name = name.strip("/")
        return f"{relroot}/{name}" if relroot else name

    def _candidates(self, name: str) -> List[str]:
        """Generate possible dataset entry names for an attribute-like token."""
        if not name:
            return []
        candidates = [name]

        def add(candidate: str) -> None:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        stripped = name[5:] if name.startswith("file_") else None
        add(stripped or "")

        dotted = name.replace("_", ".")
        add(dotted if dotted != name else "")

        if stripped:
            dotted_stripped = stripped.replace("_", ".")
            add(dotted_stripped)

        return candidates

    def _resolve_entry(self, relpath: str) -> Optional[Union["ZippedFile", "DatasetFile"]]:
        """Return the file-like entry object for a dataset-relative path."""
        relpath = relpath.strip("/")
        parent, _, leaf = relpath.rpartition("/")
        dirpath = parent
        entries = self.fs.iterdir(dirpath)
        for entry in entries:
            if entry.name == leaf and entry.is_file():
                return cast(Union["ZippedFile", "DatasetFile"], entry)
        return None

    def open(self, name: str):
        """Open a dataset-relative entry with best-effort typing.

        Attempts to parse JCAMP parameters first; falls back to text or binary
        buffers when parsing fails.
        """
        if name.startswith("_"):
            raise FileNotFoundError(name)

        for candidate in self._candidates(name):
            path = self._full_path(candidate)
            cache_key = f"{path}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

            entry = self._resolve_entry(path)
            if entry is None:
                continue

            data = entry.read()

            param = None
            if Parameters._looks_like_jcamp(data):
                try:
                    param = Parameters(data)
                except Exception:
                    param = None
            if param is not None:
                self._cache[cache_key] = param
                return param

            if _is_probably_text(data):
                try:
                    text = data.decode("utf-8")
                    obj = io.StringIO(text)
                except UnicodeDecodeError:
                    obj = io.BytesIO(data)
            else:
                obj = io.BytesIO(data)

            self._cache[cache_key] = obj
            return obj

        raise FileNotFoundError(name)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.open(name)
        except FileNotFoundError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, key: str):
        """Dictionary-style access to files (supports names not valid as attributes)."""
        return self.open(str(key))

    def listdir(self, relpath: str = "") -> List[str]:
        """List entries under this node (dirs first, then files)."""
        target = self._full_path(relpath)
        return self.fs.listdir(target)

    def iterdir(self, relpath: str = ""):
        """Iterate over entries under this node as objects (dirs first, then files)."""
        target = self._full_path(relpath)
        for entry in self.fs.iterdir(target):
            yield entry
