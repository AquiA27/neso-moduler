"""Sentiment analysis service for customer mood detection.

Analyzes customer messages to detect emotional state and provide
appropriate product recommendations.
"""

from __future__ import annotations

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..core.config import settings
from ..llm import get_llm_provider

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    mood: str  # Primary mood category
    confidence: float  # 0-1
    keywords_matched: List[str]  # Matched keywords
    tone: str  # Response tone to use
    recommended_categories: List[str]
    suggested_products: List[str]
    response_template: Optional[str] = None


class SentimentAnalyzer:
    """Analyze customer sentiment and recommend appropriate responses."""

    # Sentiment categories from schema_registry.json
    SENTIMENT_CATEGORIES = {
        "uzgun": {
            "keywords": ["üzgün", "kötü", "mutsuz", "depresif", "moral bozuk", "üzülmüş", "hüzünlü"],
            "recommended_categories": ["Sıcak İçecekler", "Tatlılar"],
            "suggested_products": ["Sıcak Çikolata", "Türk Kahvesi", "Waffle", "Çikolatalı Kek"],
            "tone": "empatik",
            "response_template": "Anlıyorum, zor bir gün geçiriyorsunuz. Size {product} önerebilirim, moral verir."
        },
        "hasta": {
            "keywords": ["hasta", "grip", "başım ağrı", "mide", "ateş", "soğuk algınlığı", "nezle", "boğaz"],
            "recommended_categories": ["Bitki Çayları", "Çorbalar", "Sıcak İçecekler"],
            "suggested_products": ["Ihlamur", "Papatya Çayı", "Zencefil Çayı", "Mercimek Çorbası"],
            "tone": "şefkatli",
            "response_template": "Geçmiş olsun. {product} size iyi gelir, hemen hazırlayalım."
        },
        "mutlu": {
            "keywords": ["mutlu", "harika", "mükemmel", "güzel", "keyifli", "muhteşem", "süper"],
            "recommended_categories": ["Özel Tatlılar", "Premium Kahveler", "Soğuk İçecekler"],
            "suggested_products": ["Cheesecake", "Latte", "Frappuccino", "Tiramisu"],
            "tone": "coşkulu",
            "response_template": "Ne güzel! Bu özel anınızı {product} ile taçlandıralım mı?"
        },
        "stresli": {
            "keywords": ["stresli", "yorgun", "bitkin", "gergin", "sınav", "iş", "yoğun", "bunaldım"],
            "recommended_categories": ["Enerjik İçecekler", "Kahve", "Pratik Atıştırmalıklar"],
            "suggested_products": ["Espresso", "Americano", "Double Shot", "Sandviç"],
            "tone": "destekleyici",
            "response_template": "Zor bir gün gibi görünüyor. {product} enerjinizi yükseltir."
        },
        "acikti": {
            "keywords": ["çok aç", "aç", "açım", "acıktım", "doyurucu", "midem", "karın"],
            "recommended_categories": ["Tuzlular", "Ana Yemekler", "Doyurucu Atıştırmalıklar"],
            "suggested_products": ["Tost", "Sandviç", "Börek", "Makarna"],
            "tone": "hızlı_çözüm",
            "response_template": "Hemen doyurucu bir şeyler hazırlayalım. {product} nasıl olur?"
        },
        "nostalji": {
            "keywords": ["eskiden", "annem", "çocukken", "hatırlatıyor", "nostalji", "geçmiş"],
            "recommended_categories": ["Geleneksel", "Ev Yapımı"],
            "suggested_products": ["Türk Kahvesi", "Sütlaç", "Baklava", "Ayran"],
            "tone": "sıcak",
            "response_template": "O günleri hatırlatacak {product} önerebilirim."
        }
    }

    def __init__(self, schema_registry: Optional[Dict] = None):
        """Initialize sentiment analyzer.

        Args:
            schema_registry: Optional schema registry with sentiment_categories
        """
        self.schema_registry = schema_registry or {}

        # Load sentiment categories from schema if available
        if "sentiment_categories" in self.schema_registry:
            self.SENTIMENT_CATEGORIES.update(self.schema_registry["sentiment_categories"])

        self.llm_provider = None
        try:
            self.llm_provider = get_llm_provider()
        except Exception as e:
            logger.warning(f"LLM provider not available for sentiment analysis: {e}")

    def normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        if not text:
            return ""
        return text.lower().strip()

    def keyword_based_sentiment(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment using keyword matching.

        Args:
            text: Input text

        Returns:
            SentimentResult if match found, else None
        """
        normalized = self.normalize_text(text)

        # Check each sentiment category
        best_match = None
        best_score = 0

        for mood, config in self.SENTIMENT_CATEGORIES.items():
            keywords = config.get("keywords", [])
            matched = []

            for keyword in keywords:
                if keyword.lower() in normalized:
                    matched.append(keyword)

            if matched:
                score = len(matched) / len(keywords)  # Proportion of keywords matched

                if score > best_score:
                    best_score = score
                    best_match = SentimentResult(
                        mood=mood,
                        confidence=min(0.95, 0.6 + score * 0.4),  # Scale 0.6-0.95
                        keywords_matched=matched,
                        tone=config.get("tone", "neutral"),
                        recommended_categories=config.get("recommended_categories", []),
                        suggested_products=config.get("suggested_products", []),
                        response_template=config.get("response_template")
                    )

        if best_match:
            logger.debug(
                f"Keyword-based sentiment: {best_match.mood} "
                f"(confidence={best_match.confidence:.2f}, "
                f"keywords={best_match.keywords_matched})"
            )

        return best_match

    async def llm_based_sentiment(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment using LLM.

        Args:
            text: Input text

        Returns:
            SentimentResult if successful, else None
        """
        if not self.llm_provider:
            return None

        try:
            # Build prompt
            categories_list = ", ".join(self.SENTIMENT_CATEGORIES.keys())

            prompt = f"""Analyze the emotional state of this customer message and classify it into one of these categories: {categories_list}

Customer message: "{text}"

Respond in JSON format:
{{
    "mood": "category_name",
    "confidence": 0.85,
    "reasoning": "brief explanation"
}}

If no strong emotion detected, use "neutral" as mood with low confidence."""

            # Call LLM (using bi_analysis task type for low temperature/deterministic)
            response = await self.llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                task_type="bi_analysis"
            )

            # Parse response
            try:
                result_json = json.loads(response.strip())
                mood = result_json.get("mood", "neutral")
                confidence = float(result_json.get("confidence", 0.5))

                # If mood is in our categories, return result
                if mood in self.SENTIMENT_CATEGORIES:
                    config = self.SENTIMENT_CATEGORIES[mood]

                    return SentimentResult(
                        mood=mood,
                        confidence=confidence,
                        keywords_matched=[],
                        tone=config.get("tone", "neutral"),
                        recommended_categories=config.get("recommended_categories", []),
                        suggested_products=config.get("suggested_products", []),
                        response_template=config.get("response_template")
                    )
                else:
                    logger.debug(f"LLM returned unrecognized mood: {mood}")
                    return None

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse LLM sentiment response: {e}")
                return None

        except Exception as e:
            logger.error(f"LLM sentiment analysis failed: {e}", exc_info=True)
            return None

    async def analyze(
        self,
        text: str,
        use_llm: bool = True
    ) -> SentimentResult:
        """Analyze customer sentiment.

        Args:
            text: Customer message
            use_llm: Whether to use LLM as fallback

        Returns:
            SentimentResult with detected mood and recommendations
        """
        if not text or not text.strip():
            return SentimentResult(
                mood="neutral",
                confidence=0.0,
                keywords_matched=[],
                tone="neutral",
                recommended_categories=[],
                suggested_products=[]
            )

        # Try keyword-based first (fast)
        result = self.keyword_based_sentiment(text)

        # If keyword match is strong, return it
        if result and result.confidence >= 0.7:
            logger.info(f"Sentiment detected (keyword): {result.mood} ({result.confidence:.2f})")
            return result

        # Try LLM-based as fallback (slower but more accurate)
        if use_llm and self.llm_provider:
            llm_result = await self.llm_based_sentiment(text)
            if llm_result and llm_result.confidence >= 0.6:
                logger.info(f"Sentiment detected (LLM): {llm_result.mood} ({llm_result.confidence:.2f})")
                return llm_result

        # Return keyword result if available, else neutral
        if result:
            logger.info(f"Sentiment detected (low confidence): {result.mood} ({result.confidence:.2f})")
            return result

        logger.debug("No sentiment detected, returning neutral")
        return SentimentResult(
            mood="neutral",
            confidence=0.5,
            keywords_matched=[],
            tone="neutral",
            recommended_categories=[],
            suggested_products=[]
        )

    def get_response_template(self, mood: str, product: str) -> str:
        """Get formatted response template for a mood.

        Args:
            mood: Mood category
            product: Product name to insert

        Returns:
            Formatted response text
        """
        if mood not in self.SENTIMENT_CATEGORIES:
            return f"Size {product} önerebilirim."

        template = self.SENTIMENT_CATEGORIES[mood].get("response_template", "Size {product} önerebilirim.")
        return template.format(product=product)


# Global instance
_sentiment_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer(schema_registry: Optional[Dict] = None) -> SentimentAnalyzer:
    """Get global sentiment analyzer instance."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer(schema_registry=schema_registry)
    return _sentiment_analyzer
