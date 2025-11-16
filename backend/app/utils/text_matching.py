"""Basit metin normalize ve benzerlik yardımcıları."""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Iterable, List, Optional, Tuple


def normalize(text: str) -> str:
    """Turkish-friendly normalize: lowercase + accent removal + trim."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def similarity(a: str, b: str) -> float:
    """Return similarity ratio between two strings."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def closest_match(query: str, candidates: Iterable[str], threshold: float = 0.6) -> Optional[Tuple[str, float]]:
    normalize_query = normalize(query)
    best_match: Optional[Tuple[str, float]] = None
    for candidate in candidates:
        score = difflib.SequenceMatcher(None, normalize_query, normalize(candidate)).ratio()
        if score >= threshold and (best_match is None or score > best_match[1]):
            best_match = (candidate, score)
    return best_match


def extract_keywords(text: str, min_len: int = 3) -> List[str]:
    tokens = normalize(text).split()
    return [tok for tok in tokens if len(tok) >= min_len]



