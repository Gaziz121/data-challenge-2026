"""Strict JSON utilities: fail closed without echoing private input."""

import hashlib
import json
from pathlib import Path


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonstandard JSON constant")


def parse_json(value):
    try:
        return json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid JSON: malformed, duplicate key or nonstandard constant") from None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_checklist(path=None):
    from .schemas import Checklist
    target = Path(path) if path else Path(__file__).parent / "checklists/official-v2.json"
    return Checklist.model_validate(parse_json(target.read_bytes()))
