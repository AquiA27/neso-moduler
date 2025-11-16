from __future__ import annotations

"""Intent tespiti ve trigger yönetimi araçları."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import logging
import math
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

TRIGGER_STORE_PATH = Path(__file__).resolve().parents[1] / "config" / "triggers.json"

logger = logging.getLogger("intent_detector")


def normalize(text: str) -> str:
    """Metni küçük harfe çevir, noktalama ve ekstra boşlukları temizle."""
    if not text:
        return ""
    text = text.lower()
    replacements = {
        "cay": "çay",
        " cay": " çay",
        " abi": " abi",
        "varmi": "var mı",
        " varmı": " var mı",
    }
    for src, target in replacements.items():
        text = text.replace(src, target)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"[^\w\sçğıöşü]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_triggers(path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Trigger listesini JSON dosyasından yükle."""
    target = Path(path) if path else TRIGGER_STORE_PATH
    if target.exists():
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def _save_triggers(triggers: Dict[str, List[str]], path: Optional[Path] = None) -> None:
    target = Path(path) if path else TRIGGER_STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(triggers, handle, ensure_ascii=False, indent=2)


def add_trigger(intent: str, phrase: str, path: Optional[Path] = None) -> None:
    """Yeni trigger ekle."""
    triggers = load_triggers(path)
    triggers.setdefault(intent, [])
    if phrase not in triggers[intent]:
        triggers[intent].append(phrase)
        _save_triggers(triggers, path)


def remove_trigger(intent: str, phrase: str, path: Optional[Path] = None) -> None:
    """Belirtilen trigger'ı sil."""
    triggers = load_triggers(path)
    phrases = triggers.get(intent)
    if not phrases:
        return
    if phrase in phrases:
        phrases.remove(phrase)
        _save_triggers(triggers, path)


TR_NUMBER_WORDS = {
    "bir": 1,
    "iki": 2,
    "üç": 3,
    "dört": 4,
    "beş": 5,
    "alti": 6,
    "altı": 6,
    "yedi": 7,
    "sekiz": 8,
    "dokuz": 9,
    "on": 10,
}


def extract_quantity(text: str) -> int:
    """Metin içinden adet bilgisini çıkar."""
    if not text:
        return 1
    digits = re.findall(r"\d+", text)
    if digits:
        return max(1, int(digits[0]))
    normalized = normalize(text)
    for word, value in TR_NUMBER_WORDS.items():
        if word in normalized.split():
            return value
    return 1


def _jaccard_score(a: str, b: str, n: int = 3) -> float:
    def ngrams(text: str) -> Iterable[str]:
        return {text[i : i + n] for i in range(len(text) - n + 1)} or {text}

    set_a, set_b = ngrams(a), ngrams(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def _partial_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    best = 0.0
    window = len(b) - len(a)
    for i in range(window + 1):
        candidate = b[i : i + len(a)]
        best = max(best, SequenceMatcher(None, a, candidate).ratio())
        if best == 1.0:
            break
    return best


def _embedding_cosine(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(y * y for y in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def detect_intent(
    text: str,
    *,
    triggers: Optional[Dict[str, List[str]]] = None,
    embed_fn: Optional[Callable[[str], List[float]]] = None,
    review_queue: Optional[List[Dict[str, str]]] = None,
    thresholds: Tuple[float, float] = (0.9, 0.6),
) -> Dict[str, object]:
    """Intent tespiti yap."""
    if not text:
        return {
            "intent": None,
            "matched_trigger": None,
            "confidence": 0.0,
            "method_scores": {"rule": 0.0, "fuzzy": 0.0, "phonetic": 0.0, "embedding": 0.0},
            "suggested_slot": {"adet": 1},
            "confidence_band": "unknown",
        }

    triggers = triggers or load_triggers()
    normalized_input = normalize(text)
    high_threshold, low_threshold = thresholds
    weights = {"rule": 0.4, "fuzzy": 0.3, "phonetic": 0.2, "embedding": 0.1}
    best_result = None
    input_embedding = embed_fn(normalized_input) if embed_fn else None

    for intent, phrases in triggers.items():
        method_scores = {"rule": 0.0, "fuzzy": 0.0, "phonetic": 0.0, "embedding": 0.0}
        best_phrase = None
        best_phrase_score = -1.0

        for phrase in phrases:
            normalized_phrase = normalize(phrase)
            if normalized_input == normalized_phrase:
                rule_score = 1.0
            elif normalized_phrase in normalized_input:
                rule_score = 0.9
            else:
                rule_score = 0.0
            base_ratio = SequenceMatcher(None, normalized_input, normalized_phrase).ratio()
            partial = _partial_ratio(normalized_input, normalized_phrase)
            fuzzy_score = max(base_ratio, partial)
            phonetic_score = _jaccard_score(normalized_input, normalized_phrase)
            embedding_score = 0.0
            if input_embedding is not None:
                phrase_embedding = embed_fn(normalized_phrase)
                embedding_score = _embedding_cosine(input_embedding, phrase_embedding)

            for key, value in zip(
                ("rule", "fuzzy", "phonetic", "embedding"),
                (rule_score, fuzzy_score, phonetic_score, embedding_score),
            ):
                method_scores[key] = max(method_scores[key], value)

            combined_score = sum(method_scores[k] * weights[k] for k in weights)
            if combined_score > best_phrase_score:
                best_phrase_score = combined_score
                best_phrase = phrase

        confidence = sum(method_scores[k] * weights[k] for k in weights)
        if not best_result or confidence > best_result["confidence"]:
            best_result = {
                "intent": intent,
                "matched_trigger": best_phrase,
                "confidence": confidence,
                "method_scores": method_scores,
            }

    if not best_result:
        best_result = {
            "intent": None,
            "matched_trigger": None,
            "confidence": 0.0,
            "method_scores": {"rule": 0.0, "fuzzy": 0.0, "phonetic": 0.0, "embedding": 0.0},
        }

    quantity = extract_quantity(text)
    suggested_slot = {"adet": quantity}
    if best_result["intent"] == "siparis_cay":
        suggested_slot["urun"] = "Çay"

    confidence = best_result["confidence"]
    band = "unknown"
    if confidence >= high_threshold:
        band = "high"
    elif confidence >= low_threshold:
        band = "ambiguous"

    result = {
        **best_result,
        "suggested_slot": suggested_slot,
        "confidence_band": band,
    }

    logger.info(
        "intent_detected",
        extra={
            "intent": result["intent"],
            "confidence": confidence,
            "method_scores": result["method_scores"],
            "text": text,
        },
    )

    if review_queue is not None and confidence < low_threshold:
        review_queue.append({"text": text, "intent": result["intent"], "confidence": confidence})

    return result

