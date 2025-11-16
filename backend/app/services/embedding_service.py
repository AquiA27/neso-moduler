"""Embedding service for menu items using OpenAI API.

This service converts text to vector embeddings for semantic search.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from openai import AsyncOpenAI, OpenAIError

from ..core.config import settings
from ..db.database import db

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    text: str
    embedding: List[float]
    model: str
    token_count: int


class EmbeddingService:
    """Service for generating and managing text embeddings."""

    EMBEDDING_MODEL = "text-embedding-ada-002"
    EMBEDDING_DIMENSION = 1536
    MAX_BATCH_SIZE = 100  # OpenAI recommends max 100 inputs per request

    def __init__(self):
        """Initialize the embedding service."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set. Embedding service will not work.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions)

        Raises:
            OpenAIError: If API call fails
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Check OPENAI_API_KEY.")

        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.EMBEDDING_DIMENSION

        try:
            response = await self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text.strip()
            )

            embedding = response.data[0].embedding

            logger.debug(
                f"Generated embedding for text (length={len(text)}), "
                f"tokens={response.usage.total_tokens}"
            )

            return embedding

        except OpenAIError as e:
            logger.error(f"OpenAI API error during embedding: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during embedding: {e}", exc_info=True)
            raise

    async def batch_embed(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Batch size (default: MAX_BATCH_SIZE)

        Returns:
            List of embedding results
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Check OPENAI_API_KEY.")

        if not texts:
            return []

        batch_size = batch_size or self.MAX_BATCH_SIZE
        results: List[EmbeddingResult] = []

        # Filter out empty texts
        valid_texts = [(i, t.strip()) for i, t in enumerate(texts) if t and t.strip()]

        if not valid_texts:
            logger.warning("All texts were empty, returning zero vectors")
            return [
                EmbeddingResult(
                    text=t,
                    embedding=[0.0] * self.EMBEDDING_DIMENSION,
                    model=self.EMBEDDING_MODEL,
                    token_count=0
                )
                for t in texts
            ]

        # Process in batches
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]
            batch_texts = [t for _, t in batch]

            try:
                response = await self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=batch_texts
                )

                for j, embedding_data in enumerate(response.data):
                    original_idx, original_text = batch[j]
                    results.append(EmbeddingResult(
                        text=original_text,
                        embedding=embedding_data.embedding,
                        model=response.model,
                        token_count=response.usage.total_tokens // len(batch_texts)
                    ))

                logger.info(
                    f"Generated {len(batch_texts)} embeddings "
                    f"(batch {i//batch_size + 1}/{(len(valid_texts)-1)//batch_size + 1}), "
                    f"tokens={response.usage.total_tokens}"
                )

                # Rate limiting: small delay between batches
                if i + batch_size < len(valid_texts):
                    await asyncio.sleep(0.1)

            except OpenAIError as e:
                logger.error(f"OpenAI API error during batch embedding: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during batch embedding: {e}", exc_info=True)
                raise

        return results

    async def embed_menu_item(
        self,
        menu_id: int,
        sube_id: int,
        product_name: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        aliases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate and store embedding for a menu item.

        Args:
            menu_id: Menu item ID
            sube_id: Branch ID
            product_name: Product name
            category: Product category
            description: Product description
            aliases: Alternative names

        Returns:
            Dictionary with menu_id, embedding_id, and metadata
        """
        # Build comprehensive text for embedding
        text_parts = [product_name]

        if category:
            text_parts.append(f"Kategori: {category}")

        if description:
            text_parts.append(description)

        if aliases:
            text_parts.append(f"Alternatif isimler: {', '.join(aliases)}")

        full_text = " | ".join(text_parts)

        # Generate embedding
        try:
            embedding = await self.embed(full_text)
        except Exception as e:
            logger.error(f"Failed to generate embedding for menu_id={menu_id}: {e}")
            raise

        # Store in database
        metadata = {
            "product_name": product_name,
            "category": category,
            "aliases": aliases or [],
            "has_description": bool(description)
        }

        # Convert embedding to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        try:
            # Check if embedding already exists
            existing = await db.fetch_one(
                """
                SELECT id FROM menu_embeddings
                WHERE menu_id = :menu_id AND sube_id = :sube_id
                """,
                {"menu_id": menu_id, "sube_id": sube_id}
            )

            if existing:
                # Update existing
                await db.execute(
                    f"""
                    UPDATE menu_embeddings
                    SET embedding = '{embedding_str}'::vector,
                        metadata = :metadata,
                        updated_at = NOW()
                    WHERE id = :id
                    """,
                    {
                        "id": existing["id"],
                        "metadata": json.dumps(metadata)
                    }
                )
                embedding_id = existing["id"]
                logger.info(f"Updated embedding for menu_id={menu_id}")
            else:
                # Insert new
                result = await db.fetch_one(
                    f"""
                    INSERT INTO menu_embeddings (menu_id, sube_id, embedding, metadata)
                    VALUES (:menu_id, :sube_id, '{embedding_str}'::vector, :metadata)
                    RETURNING id
                    """,
                    {
                        "menu_id": menu_id,
                        "sube_id": sube_id,
                        "metadata": json.dumps(metadata)
                    }
                )
                embedding_id = result["id"]
                logger.info(f"Created embedding for menu_id={menu_id}")

            return {
                "menu_id": menu_id,
                "embedding_id": embedding_id,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Failed to store embedding for menu_id={menu_id}: {e}", exc_info=True)
            raise

    async def sync_menu_embeddings(self, sube_id: int, force: bool = False) -> Dict[str, int]:
        """Synchronize embeddings for all menu items in a branch.

        Args:
            sube_id: Branch ID
            force: If True, regenerate all embeddings even if they exist

        Returns:
            Statistics: {created, updated, skipped, errors}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Get all active menu items
        menu_items = await db.fetch_all(
            """
            SELECT id, ad, kategori, aciklama
            FROM menu
            WHERE sube_id = :sube_id AND aktif = TRUE
            ORDER BY id
            """,
            {"sube_id": sube_id}
        )

        if not menu_items:
            logger.warning(f"No active menu items found for sube_id={sube_id}")
            return stats

        logger.info(f"Syncing embeddings for {len(menu_items)} menu items (sube_id={sube_id})")

        for item in menu_items:
            menu_id = item["id"]
            product_name = item["ad"]
            category = item["kategori"] if "kategori" in item.keys() else None
            description = item["aciklama"] if "aciklama" in item.keys() else None

            try:
                # Check if embedding exists
                if not force:
                    existing = await db.fetch_one(
                        """
                        SELECT id FROM menu_embeddings
                        WHERE menu_id = :menu_id AND sube_id = :sube_id
                        """,
                        {"menu_id": menu_id, "sube_id": sube_id}
                    )

                    if existing:
                        stats["skipped"] += 1
                        continue

                # Generate and store embedding
                result = await self.embed_menu_item(
                    menu_id=menu_id,
                    sube_id=sube_id,
                    product_name=product_name,
                    category=category,
                    description=description
                )

                if force or not existing:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1

            except Exception as e:
                logger.error(f"Error syncing embedding for menu_id={menu_id}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Embedding sync completed for sube_id={sube_id}: "
            f"created={stats['created']}, updated={stats['updated']}, "
            f"skipped={stats['skipped']}, errors={stats['errors']}"
        )

        # Create vector index if enough data
        if stats["created"] + stats["updated"] >= 100:
            await self.create_vector_index()

        return stats

    async def create_vector_index(self) -> bool:
        """Create IVFFlat index for fast vector similarity search.

        Note: This requires at least 100 rows of data for clustering.

        Returns:
            True if index was created successfully
        """
        try:
            # Check if index already exists
            index_exists = await db.fetch_one(
                """
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'menu_embeddings_vector_idx'
                """
            )

            if index_exists:
                logger.info("Vector index already exists")
                return True

            # Count embeddings
            count_result = await db.fetch_one(
                "SELECT COUNT(*) as cnt FROM menu_embeddings"
            )
            count = count_result["cnt"] if count_result else 0

            if count < 100:
                logger.warning(
                    f"Not enough data for vector index (need >=100, have {count}). "
                    "Will use sequential scan until more data is available."
                )
                return False

            # Create index
            logger.info(f"Creating vector index for {count} embeddings...")

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS menu_embeddings_vector_idx
                ON menu_embeddings
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )

            logger.info("Vector index created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create vector index: {e}", exc_info=True)
            return False

    async def search_similar(
        self,
        query_text: str,
        sube_id: int,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar menu items using semantic similarity.

        Args:
            query_text: Search query
            sube_id: Branch ID
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of matching products with similarity scores
        """
        if not query_text or not query_text.strip():
            return []

        # Generate query embedding
        try:
            query_embedding = await self.embed(query_text)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []

        # Search for similar embeddings using cosine similarity
        try:
            # Convert embedding to PostgreSQL vector format string
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # Use f-string for embedding (safe - it's float values) and params for user inputs
            query = f"""
                SELECT
                    me.menu_id,
                    me.metadata,
                    m.ad AS product_name,
                    m.kategori AS category,
                    m.fiyat AS price,
                    1 - (me.embedding <=> '{embedding_str}'::vector) AS similarity
                FROM menu_embeddings me
                JOIN menu m ON m.id = me.menu_id
                WHERE me.sube_id = :sube_id
                  AND m.aktif = TRUE
                  AND (1 - (me.embedding <=> '{embedding_str}'::vector)) >= :threshold
                ORDER BY me.embedding <=> '{embedding_str}'::vector
                LIMIT :limit
            """

            results = await db.fetch_all(
                query,
                {
                    "sube_id": sube_id,
                    "threshold": threshold,
                    "limit": limit
                }
            )

            matches = []
            for row in results:
                matches.append({
                    "menu_id": row["menu_id"],
                    "product_name": row["product_name"],
                    "category": row["category"],
                    "price": float(row["price"]) if row["price"] else 0.0,
                    "similarity": float(row["similarity"]),
                    "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                })

            logger.debug(
                f"Semantic search for '{query_text}' found {len(matches)} matches "
                f"(sube_id={sube_id}, threshold={threshold})"
            )

            return matches

        except Exception as e:
            logger.error(f"Failed to search similar embeddings: {e}", exc_info=True)
            return []


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
