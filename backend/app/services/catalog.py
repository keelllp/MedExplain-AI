"""Loader for the biomarker catalog (shared by extraction + abnormality services)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "biomarker_catalog.yaml"


@lru_cache
def load_catalog() -> dict:
    """Parse and cache the biomarker catalog (canonical_name -> entry dict).

    Validates the structure so a malformed YAML (e.g. a top-level list) can't be cached
    and then break every analysis with an AttributeError. lru_cache never memoizes the
    raised exception, so a fixed file is picked up on the next call.
    """
    with open(_CATALOG_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError("biomarker_catalog.yaml must be a mapping of canonical_name -> entry dict")
    return data
