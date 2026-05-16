from functools import lru_cache
from typing import Dict, List, Set

import yaml

from core.config import settings


@lru_cache(maxsize=1)
def load_synonyms() -> Dict[str, List[str]]:
    """Load the synonym dictionary from disk once.

    Hard-fails at first call if the YAML is missing or malformed —
    we want loud failure at startup, not silent skill-matching degradation.
    """
    path = settings.SYNONYMS_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Synonyms YAML at {path} must be a mapping, got {type(raw).__name__}")
    out: Dict[str, List[str]] = {}
    for canonical, aliases in raw.items():
        if not isinstance(aliases, list):
            raise ValueError(f"Synonyms for '{canonical}' must be a list, got {type(aliases).__name__}")
        out[str(canonical).lower()] = [str(a).lower() for a in aliases]
    return out


def expand_with_synonyms(term: str, syns: Dict[str, List[str]]) -> Set[str]:
    """Return the lowercased term plus all of its synonyms (canonical + aliases)."""
    lowered = term.lower()
    out: Set[str] = {lowered}
    for canonical, aliases in syns.items():
        if lowered == canonical or lowered in aliases:
            out.add(canonical)
            out.update(aliases)
    return out
