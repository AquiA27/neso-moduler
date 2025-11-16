"""Automatic embedding generation hooks for menu changes.

This module provides hooks that automatically generate embeddings
when menu items are created or updated.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any

from ..services.embedding_service import get_embedding_service
from ..db.database import db

logger = logging.getLogger(__name__)


async def on_menu_created(
    menu_id: int,
    sube_id: int,
    product_name: str,
    category: Optional[str] = None,
    description: Optional[str] = None
) -> bool:
    """Hook called when a new menu item is created.

    Args:
        menu_id: ID of the newly created menu item
        sube_id: Branch ID
        product_name: Product name
        category: Product category
        description: Product description

    Returns:
        True if embedding was generated successfully
    """
    try:
        embedding_service = get_embedding_service()

        logger.info(f"Generating embedding for new menu item: {product_name} (id={menu_id})")

        await embedding_service.embed_menu_item(
            menu_id=menu_id,
            sube_id=sube_id,
            product_name=product_name,
            category=category,
            description=description
        )

        logger.info(f"Successfully generated embedding for menu_id={menu_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to generate embedding for menu_id={menu_id}: {e}",
            exc_info=True
        )
        # Don't raise - embedding generation failure should not block menu creation
        return False


async def on_menu_updated(
    menu_id: int,
    sube_id: int,
    product_name: str,
    category: Optional[str] = None,
    description: Optional[str] = None
) -> bool:
    """Hook called when a menu item is updated.

    Args:
        menu_id: ID of the updated menu item
        sube_id: Branch ID
        product_name: Updated product name
        category: Updated product category
        description: Updated product description

    Returns:
        True if embedding was updated successfully
    """
    try:
        embedding_service = get_embedding_service()

        logger.info(f"Updating embedding for menu item: {product_name} (id={menu_id})")

        await embedding_service.embed_menu_item(
            menu_id=menu_id,
            sube_id=sube_id,
            product_name=product_name,
            category=category,
            description=description
        )

        logger.info(f"Successfully updated embedding for menu_id={menu_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to update embedding for menu_id={menu_id}: {e}",
            exc_info=True
        )
        # Don't raise - embedding update failure should not block menu update
        return False


async def on_menu_deleted(menu_id: int, sube_id: int) -> bool:
    """Hook called when a menu item is deleted.

    Args:
        menu_id: ID of the deleted menu item
        sube_id: Branch ID

    Returns:
        True if embedding was deleted successfully
    """
    try:
        logger.info(f"Deleting embedding for menu_id={menu_id}")

        await db.execute(
            """
            DELETE FROM menu_embeddings
            WHERE menu_id = :menu_id AND sube_id = :sube_id
            """,
            {"menu_id": menu_id, "sube_id": sube_id}
        )

        logger.info(f"Successfully deleted embedding for menu_id={menu_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to delete embedding for menu_id={menu_id}: {e}",
            exc_info=True
        )
        return False


async def sync_all_embeddings_background(sube_id: int):
    """Background task to sync all menu embeddings for a branch.

    This can be called periodically or after bulk menu changes.

    Args:
        sube_id: Branch ID
    """
    try:
        logger.info(f"Starting background embedding sync for sube_id={sube_id}")

        embedding_service = get_embedding_service()
        stats = await embedding_service.sync_menu_embeddings(sube_id=sube_id, force=False)

        logger.info(
            f"Background embedding sync completed for sube_id={sube_id}: "
            f"created={stats['created']}, updated={stats['updated']}, "
            f"skipped={stats['skipped']}, errors={stats['errors']}"
        )

    except Exception as e:
        logger.error(
            f"Background embedding sync failed for sube_id={sube_id}: {e}",
            exc_info=True
        )


# Helper function to schedule background sync
def schedule_embedding_sync(sube_id: int):
    """Schedule a background embedding sync task.

    This function creates a background task that doesn't block the response.

    Args:
        sube_id: Branch ID
    """
    asyncio.create_task(sync_all_embeddings_background(sube_id))
    logger.info(f"Scheduled background embedding sync for sube_id={sube_id}")
