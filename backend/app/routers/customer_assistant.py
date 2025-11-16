"""Customer Assistant Router - Main entry point for customer interactions.

This router handles:
- Customer orders with NLU
- Semantic + Fuzzy product matching
- Sentiment analysis
- Product recommendations
- Confirmation workflows
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from ..core.deps import get_current_user, get_sube_id
from ..db.database import db
from ..services.context_manager import context_manager
import json

from .assistant import (
    ChatRequest,
    chat_smart as assistant_chat_smart,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer-assistant", tags=["Customer Assistant"])


# ==================== REQUEST/RESPONSE MODELS ====================

class CustomerChatRequest(BaseModel):
    """Customer chat message."""
    text: str = Field(min_length=1, description="Customer message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for context")
    masa: Optional[str] = Field(default=None, description="Table number")


class ProductMatch(BaseModel):
    """A matched product."""
    menu_id: int
    product_name: str
    category: str
    price: float
    confidence: float
    semantic_score: float = 0.0
    fuzzy_score: float = 0.0


class ConfirmationOption(BaseModel):
    """An option for user confirmation."""
    value: str
    label: str
    menu_id: Optional[int] = None


class CustomerChatResponse(BaseModel):
    """Response to customer chat."""
    type: str  # "success", "confirmation", "options", "recommendation", "error"
    message: str
    matched_products: Optional[List[ProductMatch]] = None
    options: Optional[List[ConfirmationOption]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    intent: Optional[str] = None
    sentiment: Optional[Dict[str, Any]] = None
    audio_base64: Optional[str] = None
    conversation_id: Optional[str] = None
    detected_language: Optional[str] = None


# ==================== HELPER FUNCTIONS ====================

# ==================== MAIN ENDPOINTS ====================

@router.post("/chat", response_model=CustomerChatResponse)
async def customer_chat(
    payload: CustomerChatRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Thin wrapper that delegates to the intelligent assistant pipeline."""
    try:
        conversation_id = payload.conversation_id or f"conv_{user['id']}_{sube_id}"
        ctx = await context_manager.get(conversation_id)

        masa_value = payload.masa or ctx.masa
        if payload.masa and payload.masa != ctx.masa:
            await context_manager.update(conversation_id, masa=payload.masa)

        assistant_request = ChatRequest(
            text=payload.text,
            masa=masa_value,
            sube_id=sube_id,
            conversation_id=conversation_id,
        )

        assistant_response = await assistant_chat_smart(assistant_request)

        await context_manager.set_last_intent(conversation_id, "assistant")

        return CustomerChatResponse(
            type="success",
            message=assistant_response.reply,
            matched_products=None,
            options=None,
            recommendations=None,
            suggestions=assistant_response.suggestions,
            intent="assistant",
            sentiment={"mood": "neutral", "confidence": 1.0},
            audio_base64=assistant_response.audio_base64,
            conversation_id=assistant_response.conversation_id or conversation_id,
            detected_language=assistant_response.detected_language,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Customer chat error: {e}", exc_info=True)
        return CustomerChatResponse(
            type="error",
            message="Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."
        )


@router.post("/confirm-order")
async def confirm_order(
    menu_id: int,
    quantity: int = 1,
    masa: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Confirm and create an order.

    This is called after user confirms a product match.
    """
    try:
        # Get product details
        product = await db.fetch_one(
            "SELECT ad, fiyat FROM menu WHERE id = :id AND sube_id = :sube_id",
            {"id": menu_id, "sube_id": sube_id}
        )

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Create order item
        sepet = [{
            "urun": product["ad"],
            "adet": quantity,
            "fiyat": float(product["fiyat"]) if product["fiyat"] else 0.0
        }]

        tutar = quantity * (float(product["fiyat"]) if product["fiyat"] else 0.0)

        # Get or create adisyon
        from ..routers.adisyon import _get_or_create_adisyon

        if not masa:
            raise HTTPException(status_code=400, detail="Table number required")

        adisyon_id = await _get_or_create_adisyon(masa, sube_id)

        # Create order
        await db.execute(
            """
            INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar, created_by_username)
            VALUES (:sube_id, :masa, :adisyon_id, :sepet, 'yeni', :tutar, 'AI')
            """,
            {
                "sube_id": sube_id,
                "masa": masa,
                "adisyon_id": adisyon_id,
                "sepet": json.dumps(sepet),
                "tutar": tutar
            }
        )

        return {
            "status": "success",
            "message": f"{quantity} adet {product['ad']} siparişiniz alındı.",
            "total": tutar
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order confirmation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create order")
