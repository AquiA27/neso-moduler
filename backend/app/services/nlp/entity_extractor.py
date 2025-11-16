"""Entity extraction service for customer orders.

Extracts:
- Product names/queries
- Quantities
- Variations (size, sweetness, temperature, etc.)
- Modifiers (no sugar, extra shot, etc.)
"""

from __future__ import annotations

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Turkish number words
TR_NUMBER_WORDS = {
    "bir": 1, "iki": 2, "üç": 3, "uc": 3,
    "dört": 4, "dort": 4, "beş": 5, "bes": 5,
    "altı": 6, "alti": 6, "yedi": 7, "sekiz": 8,
    "dokuz": 9, "on": 10, "onbir": 11, "oniki": 12
}


@dataclass
class ExtractedEntity:
    """Extracted entity from text."""
    type: str  # product, quantity, variation, modifier
    value: Any
    confidence: float
    raw_text: str
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class OrderEntities:
    """Structured entities from an order text."""
    products: List[str] = field(default_factory=list)
    quantities: Dict[str, int] = field(default_factory=dict)  # product -> quantity
    variations: Dict[str, List[str]] = field(default_factory=dict)  # product -> [variations]
    modifiers: List[str] = field(default_factory=list)
    raw_entities: List[ExtractedEntity] = field(default_factory=list)
    confidence: float = 0.0


class EntityExtractor:
    """Extract structured entities from natural language orders."""

    # Skip words (greetings, fillers, etc.)
    SKIP_WORDS = {
        "merhaba", "selam", "hey", "hello", "hi",
        "lütfen", "lutfen", "rica", "ederim",
        "teşekkürler", "tesekkurler", "sağol", "sagol",
        "tane", "adet", "ve", "ile", "veya", "ya da",
        "bir", "de", "da", "mi", "mı", "mu", "mü"
    }

    # Variation keywords
    VARIATIONS = {
        "size": ["küçük", "kucuk", "orta", "büyük", "buyuk", "small", "medium", "large"],
        "sweetness": ["şekerli", "sekerli", "şekersiz", "sekersiz", "az şekerli", "bol şekerli"],
        "temperature": ["sıcak", "sicak", "soğuk", "soguk", "ılık", "ilik", "buzlu"],
        "intensity": ["hafif", "orta", "koyu", "double", "single", "tek shot", "çift shot"],
        "milk": ["sütlü", "sutlu", "sütsüz", "sutsuz", "light süt", "badem sütü", "soya sütü"],
        "sauce": ["ketçaplı", "ketcapli", "ketçapsız", "ketcapsiz", "mayonezli", "mayonezsiz"],
        "spice": ["acılı", "acili", "acısız", "acisiz", "az acı", "çok acı"]
    }

    # Flattened variation keywords for quick lookup
    ALL_VARIATIONS = set()
    for variants in VARIATIONS.values():
        ALL_VARIATIONS.update(variants)

    def __init__(self, schema_registry: Optional[Dict] = None):
        """Initialize entity extractor.

        Args:
            schema_registry: Schema registry for product variations
        """
        self.schema_registry = schema_registry or {}

        # Load product variations from schema if available
        if "product_variations" in self.schema_registry:
            for var_type, keywords in self.schema_registry["product_variations"].items():
                if var_type not in self.VARIATIONS:
                    self.VARIATIONS[var_type] = keywords
                else:
                    self.VARIATIONS[var_type].extend(keywords)
                self.ALL_VARIATIONS.update(keywords)

    def normalize_text(self, text: str) -> str:
        """Normalize text for extraction.

        Args:
            text: Raw input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower().strip()

        # Turkish character normalization (optional - keep Turkish chars for now)
        # text = text.replace("ç", "c").replace("ğ", "g")...

        # Remove excessive punctuation
        text = re.sub(r"[!?]{2,}", "!", text)
        text = re.sub(r"\.{2,}", ".", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        return text

    def extract_quantities(self, text: str) -> List[ExtractedEntity]:
        """Extract quantity mentions from text.

        Args:
            text: Input text

        Returns:
            List of quantity entities
        """
        entities = []

        # Pattern 1: Numeric quantities (1, 2, 3...)
        for match in re.finditer(r"\b(\d+)\b", text):
            quantity = int(match.group(1))
            if 0 < quantity <= 100:  # Reasonable quantity range
                entities.append(ExtractedEntity(
                    type="quantity",
                    value=quantity,
                    confidence=1.0,
                    raw_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        # Pattern 2: Word numbers (bir, iki, üç...)
        words = text.split()
        for i, word in enumerate(words):
            if word in TR_NUMBER_WORDS:
                quantity = TR_NUMBER_WORDS[word]
                entities.append(ExtractedEntity(
                    type="quantity",
                    value=quantity,
                    confidence=0.95,
                    raw_text=word,
                    start_pos=text.find(word),
                    end_pos=text.find(word) + len(word)
                ))

        return entities

    def extract_variations(self, text: str) -> List[ExtractedEntity]:
        """Extract variation keywords from text.

        Args:
            text: Input text

        Returns:
            List of variation entities
        """
        entities = []
        words = text.split()

        for word in words:
            if word in self.ALL_VARIATIONS:
                # Find which category
                category = None
                for cat, keywords in self.VARIATIONS.items():
                    if word in keywords:
                        category = cat
                        break

                entities.append(ExtractedEntity(
                    type="variation",
                    value={"category": category, "keyword": word},
                    confidence=0.9,
                    raw_text=word,
                    start_pos=text.find(word),
                    end_pos=text.find(word) + len(word)
                ))

        return entities

    def extract_product_candidates(self, text: str) -> List[ExtractedEntity]:
        """Extract potential product names from text.

        This uses pattern matching and skip-word filtering to identify
        product name candidates. Actual matching happens later with menu data.

        Args:
            text: Input text

        Returns:
            List of product candidate entities
        """
        entities = []
        words = text.split()

        # Remove skip words and variations
        filtered_words = []
        i = 0
        while i < len(words):
            word = words[i]

            # Skip if it's a skip word
            if word in self.SKIP_WORDS:
                i += 1
                continue

            # Skip if it's a number
            if word.isdigit() or word in TR_NUMBER_WORDS:
                i += 1
                continue

            # Skip if it's a variation
            if word in self.ALL_VARIATIONS:
                i += 1
                continue

            filtered_words.append(word)
            i += 1

        # Build product candidates (1-3 word sequences)
        for n_gram_size in [3, 2, 1]:  # Try longer sequences first
            for i in range(len(filtered_words) - n_gram_size + 1):
                candidate = " ".join(filtered_words[i:i + n_gram_size])

                # Skip very short candidates
                if len(candidate) < 2:
                    continue

                entities.append(ExtractedEntity(
                    type="product_candidate",
                    value=candidate,
                    confidence=0.8 / n_gram_size,  # Longer sequences = lower confidence
                    raw_text=candidate,
                    start_pos=text.find(candidate),
                    end_pos=text.find(candidate) + len(candidate)
                ))

        return entities

    def extract(self, text: str, intent: Optional[str] = None) -> OrderEntities:
        """Extract all entities from text.

        Args:
            text: Input text
            intent: Optional intent hint (e.g., "siparis", "soru")

        Returns:
            OrderEntities with extracted information
        """
        if not text or not text.strip():
            return OrderEntities()

        # Normalize text
        normalized_text = self.normalize_text(text)

        # Extract all entity types
        quantity_entities = self.extract_quantities(normalized_text)
        variation_entities = self.extract_variations(normalized_text)
        product_entities = self.extract_product_candidates(normalized_text)

        # Build OrderEntities
        order = OrderEntities()
        order.raw_entities = quantity_entities + variation_entities + product_entities

        # Populate structured fields
        for entity in product_entities:
            if entity.type == "product_candidate":
                order.products.append(entity.value)

        for entity in variation_entities:
            if entity.type == "variation":
                order.modifiers.append(entity.value["keyword"])

        # Match quantities to products (heuristic: closest quantity before product)
        for product in order.products:
            # Find the product position
            product_pos = normalized_text.find(product)

            # Find closest quantity before this position
            closest_qty = None
            closest_dist = float('inf')

            for qty_entity in quantity_entities:
                if qty_entity.start_pos < product_pos:
                    dist = product_pos - qty_entity.end_pos
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_qty = qty_entity.value

            # Default to 1 if no quantity found
            order.quantities[product] = closest_qty or 1

        # Calculate overall confidence
        if order.raw_entities:
            order.confidence = sum(e.confidence for e in order.raw_entities) / len(order.raw_entities)
        else:
            order.confidence = 0.0

        logger.debug(
            f"Extracted entities from '{text}': "
            f"products={order.products}, quantities={order.quantities}, "
            f"variations={order.modifiers}, confidence={order.confidence:.2f}"
        )

        return order


# Global instance
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor(schema_registry: Optional[Dict] = None) -> EntityExtractor:
    """Get global entity extractor instance."""
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor(schema_registry=schema_registry)
    return _entity_extractor
