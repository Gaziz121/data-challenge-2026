"""Small immutable version registry; reuse the existing Checklist contract/scorer."""

from pathlib import Path
import os
import threading

from .io import canonical, digest, parse_json
from .schemas import Checklist


class ChecklistConflict(ValueError):
    pass


class ChecklistRegistry:
    @staticmethod
    def _version_key(checklist):
        return digest({"checklist_id": checklist.checklist_id, "version": checklist.version})

    @staticmethod
    def _read(path):
        saved = parse_json(path.read_bytes())
        if not isinstance(saved, dict) or set(saved) != {"checklist", "sha256"}:
            raise ValueError("Invalid saved checklist record")
        checklist = Checklist.model_validate(saved["checklist"])
        if saved["sha256"] != digest(checklist.model_dump(mode="json")):
            raise ValueError("Saved checklist content/hash mismatch")
        return checklist

    def __init__(self, default, directory, additional=()):
        self.directory = Path(directory)
        self._lock = threading.RLock()
        self._versions = {}
        self._add(Checklist.model_validate(default.model_dump()))
        for checklist in additional:
            self._add(Checklist.model_validate(checklist.model_dump()))
        if self.directory.exists():
            for path in sorted(self.directory.glob("*.json")):
                checklist = self._read(path)
                if path.stem != self._version_key(checklist):
                    raise ValueError("Saved checklist identity/hash mismatch")
                self._add(checklist)

    def _add(self, checklist):
        key = (checklist.checklist_id, checklist.version)
        old = self._versions.get(key)
        if old and old != checklist:
            raise ChecklistConflict("Checklist version already exists with different content; use a new version")
        self._versions[key] = checklist.model_copy(deep=True)

    def get(self, reference):
        with self._lock:
            checklist = self._versions.get((reference.checklist_id, reference.version))
            if checklist is None:
                raise LookupError("Checklist version not found")
            return checklist.model_copy(deep=True)

    def list(self):
        with self._lock:
            return [{"checklist_id": c.checklist_id, "version": c.version,
                     "sha256": digest(c.model_dump(mode="json"))}
                    for _, c in sorted(self._versions.items())]

    def by_hash(self, identifier):
        with self._lock:
            for checklist in self._versions.values():
                if digest(checklist.model_dump(mode="json")) == identifier:
                    return checklist.model_copy(deep=True)
        raise LookupError("Checklist version not found")

    def save(self, checklist):
        checklist = Checklist.model_validate(checklist.model_dump())
        with self._lock:
            key = (checklist.checklist_id, checklist.version)
            if key in self._versions:
                if self._versions[key] != checklist:
                    raise ChecklistConflict("Checklist version already exists with different content; use a new version")
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            # One exclusive path per identity/version also prevents two processes
            # from publishing different contents under the same version.
            target = self.directory / (self._version_key(checklist) + ".json")
            try:
                with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
                    handle.write(canonical({"checklist": checklist.model_dump(mode="json"),
                                            "sha256": digest(checklist.model_dump(mode="json"))}) + "\n")
            except FileExistsError:
                if self._read(target) != checklist:
                    raise ChecklistConflict("Saved checklist differs; no overwrite performed") from None
            self._add(checklist)
            return {"checklist_id": checklist.checklist_id, "version": checklist.version,
                    "sha256": digest(checklist.model_dump(mode="json"))}
