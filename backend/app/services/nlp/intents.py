"""Heuristic intent classifier for customer assistant."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from ...utils.text_matching import extract_keywords


@dataclass
class IntentResult:
    intent: Optional[str]
    confidence: float
    entities: Dict[str, str]
    raw_text: str


_INTENT_KEYWORDS = {
    "stok_durumu": ["stok", "kalan", "var mı", "bitmiş", "bitecek", "rafta"],
    "menu_liste": ["menü", "menu", "neler", "ne var", "öner", "oner"],
    "aktif_adisyonlar": ["hesap", "fatura", "borç", "masa", "adisyon"],
    "satis_ozet": ["satış", "ciro", "rapor", "performans", "kaç sipariş"],
}

_ENTITY_PATTERNS = {
    "masa": re.compile(r"masa\s*(\w+)", re.IGNORECASE),
}


class IntentClassifier:
    def predict(self, text: str, *, sube_id: Optional[int] = None, masa: Optional[str] = None) -> IntentResult:
        lowered = text.lower()
        matched_intent: Optional[str] = None
        confidence = 0.0

        for intent, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in lowered)
            if score and (matched_intent is None or score > confidence * 10):
                matched_intent = intent
                confidence = min(1.0, score / max(len(keywords), 1))

        entities: Dict[str, str] = {}
        if masa:
            entities["masa"] = masa
        else:
            match = _ENTITY_PATTERNS["masa"].search(text)
            if match:
                entities["masa"] = match.group(1)

        keywords = extract_keywords(text)
        if keywords:
            entities["keywords"] = ",".join(keywords)

        if sube_id is not None:
            entities["sube_id"] = str(sube_id)

        if matched_intent is None:
            confidence = 0.0

        return IntentResult(
            intent=matched_intent,
            confidence=confidence,
            entities=entities,
            raw_text=text,
        )


intent_classifier = IntentClassifier()



