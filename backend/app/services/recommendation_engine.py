"""Recommendation engine for product suggestions.

Provides recommendations based on:
- Customer mood/sentiment
- Product popularity
- Stock availability
- User history (optional)
- Category filters
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..db.database import db

logger = logging.getLogger(__name__)


@dataclass
class ProductRecommendation:
    """A product recommendation."""
    menu_id: int
    product_name: str
    category: str
    price: float
    reason: str  # Why this was recommended
    confidence: float  # 0-1
    popularity_score: float = 0.0  # Based on sales
    stock_status: str = "yeterli"


class RecommendationEngine:
    """Generate product recommendations based on various factors."""

    def __init__(self):
        """Initialize recommendation engine."""
        pass

    async def get_popular_products(
        self,
        sube_id: int,
        limit: int = 10,
        days: int = 30,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get popular products based on recent sales.

        Args:
            sube_id: Branch ID
            limit: Maximum number of products
            days: Look back period
            categories: Optional category filters

        Returns:
            List of popular products with sales data
        """
        try:
            # Build category filter
            category_filter = ""
            params: Dict[str, Any] = {
                "sube_id": sube_id,
                "start_date": datetime.now() - timedelta(days=days),
                "limit": limit
            }

            if categories:
                category_filter = "AND m.kategori = ANY(:categories)"
                params["categories"] = categories

            query = f"""
                WITH sales_data AS (
                    SELECT
                        jsonb_array_elements(s.sepet::jsonb) AS item
                    FROM siparisler s
                    WHERE s.sube_id = :sube_id
                      AND s.durum = 'odendi'
                      AND s.created_at >= :start_date
                )
                SELECT
                    m.id AS menu_id,
                    m.ad AS product_name,
                    m.kategori AS category,
                    m.fiyat AS price,
                    COUNT(*) AS sales_count,
                    SUM((sd.item->>'adet')::float) AS total_quantity,
                    SUM((sd.item->>'adet')::float * (sd.item->>'fiyat')::float) AS total_revenue
                FROM sales_data sd
                JOIN menu m ON m.ad = (sd.item->>'urun')
                WHERE m.sube_id = :sube_id
                  AND m.aktif = TRUE
                  {category_filter}
                GROUP BY m.id, m.ad, m.kategori, m.fiyat
                ORDER BY sales_count DESC, total_revenue DESC
                LIMIT :limit
            """

            results = await db.fetch_all(query, params)

            products = []
            for row in results:
                products.append({
                    "menu_id": row["menu_id"],
                    "product_name": row["product_name"],
                    "category": row["category"],
                    "price": float(row["price"]) if row["price"] else 0.0,
                    "sales_count": row["sales_count"],
                    "total_quantity": float(row["total_quantity"]),
                    "total_revenue": float(row["total_revenue"])
                })

            return products

        except Exception as e:
            logger.error(f"Failed to get popular products: {e}", exc_info=True)
            return []

    async def check_stock_availability(
        self,
        menu_id: int,
        sube_id: int
    ) -> str:
        """Check stock status for a menu item.

        Args:
            menu_id: Menu item ID
            sube_id: Branch ID

        Returns:
            Stock status: yeterli, az, kritik, yok, bilinmiyor
        """
        try:
            # Use the vw_ai_menu_stock view
            result = await db.fetch_one(
                """
                SELECT overall_stock_status
                FROM vw_ai_menu_stock
                WHERE menu_id = :menu_id AND sube_id = :sube_id
                """,
                {"menu_id": menu_id, "sube_id": sube_id}
            )

            if result:
                return result["overall_stock_status"]
            else:
                return "bilinmiyor"

        except Exception as e:
            logger.warning(f"Failed to check stock for menu_id={menu_id}: {e}")
            return "bilinmiyor"

    async def recommend_by_mood(
        self,
        sube_id: int,
        mood: str,
        limit: int = 5,
        exclude_out_of_stock: bool = True
    ) -> List[ProductRecommendation]:
        """Recommend products based on customer mood.

        Args:
            sube_id: Branch ID
            mood: Mood category (from sentiment analyzer)
            limit: Maximum recommendations
            exclude_out_of_stock: Whether to exclude out-of-stock items

        Returns:
            List of product recommendations
        """
        # Get sentiment-based category recommendations
        from .sentiment_analyzer import get_sentiment_analyzer

        sentiment_analyzer = get_sentiment_analyzer()

        if mood not in sentiment_analyzer.SENTIMENT_CATEGORIES:
            logger.warning(f"Unknown mood: {mood}, using neutral")
            mood = "neutral"

        sentiment_config = sentiment_analyzer.SENTIMENT_CATEGORIES.get(mood, {})
        recommended_categories = sentiment_config.get("recommended_categories", [])
        suggested_products = sentiment_config.get("suggested_products", [])

        # Get products from recommended categories
        recommendations = []

        try:
            # First, try to match suggested products directly
            if suggested_products:
                for product_name in suggested_products[:limit]:
                    result = await db.fetch_one(
                        """
                        SELECT id, ad, kategori, fiyat
                        FROM menu
                        WHERE sube_id = :sube_id
                          AND aktif = TRUE
                          AND LOWER(ad) LIKE LOWER(:name)
                        LIMIT 1
                        """,
                        {"sube_id": sube_id, "name": f"%{product_name}%"}
                    )

                    if result:
                        menu_id = result["id"]
                        stock_status = await self.check_stock_availability(menu_id, sube_id)

                        if exclude_out_of_stock and stock_status == "yok":
                            continue

                        recommendations.append(ProductRecommendation(
                            menu_id=menu_id,
                            product_name=result["ad"],
                            category=result["kategori"] or "",
                            price=float(result["fiyat"]) if result["fiyat"] else 0.0,
                            reason=f"Ruh halinize uygun ({mood})",
                            confidence=0.9,
                            stock_status=stock_status
                        ))

            # Fill remaining slots with popular items from recommended categories
            if len(recommendations) < limit and recommended_categories:
                popular = await self.get_popular_products(
                    sube_id=sube_id,
                    limit=limit - len(recommendations),
                    categories=recommended_categories
                )

                for product in popular:
                    menu_id = product["menu_id"]
                    stock_status = await self.check_stock_availability(menu_id, sube_id)

                    if exclude_out_of_stock and stock_status == "yok":
                        continue

                    # Skip if already recommended
                    if any(r.menu_id == menu_id for r in recommendations):
                        continue

                    recommendations.append(ProductRecommendation(
                        menu_id=menu_id,
                        product_name=product["product_name"],
                        category=product["category"],
                        price=product["price"],
                        reason=f"Popüler seçim ({mood} için)",
                        confidence=0.75,
                        popularity_score=float(product.get("sales_count", 0)),
                        stock_status=stock_status
                    ))

            logger.info(
                f"Generated {len(recommendations)} recommendations for mood={mood}, "
                f"sube_id={sube_id}"
            )

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Failed to generate mood-based recommendations: {e}", exc_info=True)
            return []

    async def recommend_popular(
        self,
        sube_id: int,
        limit: int = 5,
        categories: Optional[List[str]] = None,
        exclude_out_of_stock: bool = True
    ) -> List[ProductRecommendation]:
        """Recommend popular products.

        Args:
            sube_id: Branch ID
            limit: Maximum recommendations
            categories: Optional category filters
            exclude_out_of_stock: Whether to exclude out-of-stock items

        Returns:
            List of product recommendations
        """
        try:
            popular = await self.get_popular_products(
                sube_id=sube_id,
                limit=limit * 2,  # Get more to account for out-of-stock
                categories=categories
            )

            recommendations = []
            for product in popular:
                menu_id = product["menu_id"]
                stock_status = await self.check_stock_availability(menu_id, sube_id)

                if exclude_out_of_stock and stock_status == "yok":
                    continue

                recommendations.append(ProductRecommendation(
                    menu_id=menu_id,
                    product_name=product["product_name"],
                    category=product["category"],
                    price=product["price"],
                    reason="En çok tercih edilen",
                    confidence=0.8,
                    popularity_score=float(product.get("sales_count", 0)),
                    stock_status=stock_status
                ))

                if len(recommendations) >= limit:
                    break

            logger.info(
                f"Generated {len(recommendations)} popular recommendations for sube_id={sube_id}"
            )

            return recommendations

        except Exception as e:
            logger.error(f"Failed to generate popular recommendations: {e}", exc_info=True)
            return []

    async def recommend(
        self,
        sube_id: int,
        mood: Optional[str] = None,
        user_history: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        limit: int = 5,
        exclude_out_of_stock: bool = True
    ) -> List[ProductRecommendation]:
        """Generate comprehensive product recommendations.

        Args:
            sube_id: Branch ID
            mood: Optional customer mood
            user_history: Optional user's previous orders
            categories: Optional category filters
            limit: Maximum recommendations
            exclude_out_of_stock: Whether to exclude out-of-stock items

        Returns:
            List of product recommendations
        """
        recommendations = []

        # 1. Mood-based recommendations (if mood provided)
        if mood:
            mood_recs = await self.recommend_by_mood(
                sube_id=sube_id,
                mood=mood,
                limit=limit,
                exclude_out_of_stock=exclude_out_of_stock
            )
            recommendations.extend(mood_recs)

        # 2. Fill remaining with popular products
        if len(recommendations) < limit:
            popular_recs = await self.recommend_popular(
                sube_id=sube_id,
                limit=limit - len(recommendations),
                categories=categories,
                exclude_out_of_stock=exclude_out_of_stock
            )

            # Add popular items that aren't already recommended
            for rec in popular_recs:
                if not any(r.menu_id == rec.menu_id for r in recommendations):
                    recommendations.append(rec)

        # Sort by confidence * popularity
        recommendations.sort(
            key=lambda r: r.confidence * (1 + r.popularity_score / 100),
            reverse=True
        )

        return recommendations[:limit]


# Global instance
_recommendation_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """Get global recommendation engine instance."""
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = RecommendationEngine()
    return _recommendation_engine
