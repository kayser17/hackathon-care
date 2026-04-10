from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


RESOURCE_DIR = Path(__file__).resolve().parent / "resources"


@lru_cache(maxsize=1)
def load_manipulation_patterns() -> list[str]:
    return _load_json_list(RESOURCE_DIR / "manipulation_patterns.json")


@lru_cache(maxsize=1)
def load_distress_patterns() -> list[str]:
    return _load_json_list(RESOURCE_DIR / "distress_patterns.json")


def _load_json_list(path: Path) -> list[str]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"Resource file {path} must contain a JSON list of strings.")
    return payload
