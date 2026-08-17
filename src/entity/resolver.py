from __future__ import annotations
import re
from difflib import SequenceMatcher
from src.models import EntityMapping

LEGAL = {"inc", "incorporated", "corp", "corporation", "llc", "ltd", "limited", "co", "company"}


def normalize(name: str) -> str:
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    tokens = [t for t in s.split() if t not in LEGAL]
    return "".join(tokens)


class EntityResolver:
    def __init__(self, canonical_names: list[str]):
        self.canonical = canonical_names
        self.index = {normalize(x): x for x in canonical_names}

    def resolve(self, raw: str, entity_type: str) -> EntityMapping:
        n = normalize(raw)
        if n in self.index:
            return EntityMapping(raw_name=raw, canonical_name=self.index[n], entity_type=entity_type, method="normalized_exact", score=1.0)
        best, score = None, 0.0
        for candidate in self.canonical:
            s = SequenceMatcher(None, n, normalize(candidate)).ratio()
            if s > score:
                best, score = candidate, s
        if best and score >= 0.90:
            return EntityMapping(raw_name=raw, canonical_name=best, entity_type=entity_type, method="fuzzy", score=score)
        return EntityMapping(raw_name=raw, canonical_name=raw.strip(), entity_type=entity_type, method="unresolved", score=score)
