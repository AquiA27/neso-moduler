# backend/app/routers/websocket_router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Any
import uuid
import logging

from ..websocket.manager import manager, Topics
from ..core.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    topics: str = Query("", description="Comma-separated topics to subscribe"),
):
    """
    WebSocket connection endpoint.
    Topics: kitchen,cashier,tables,orders,admin,waiter
    """
    connection_id = str(uuid.uuid4())
    
    try:
        await manager.connect(websocket, connection_id)
        
        # Subscribe to requested topics
        if topics:
            topic_list = [t.strip() for t in topics.split(",") if t.strip()]
            for topic in topic_list:
                if topic in [Topics.KITCHEN, Topics.CASHIER, Topics.TABLES, Topics.ORDERS, Topics.ADMIN, Topics.WAITER, Topics.STOCK]:
                    manager.subscribe(connection_id, topic)
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for client messages (ping, subscribe, unsubscribe, etc.)
                data = await websocket.receive_text()
                
                # Handle simple ping/pong
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    logger.info(f"Received message from {connection_id}: {data}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in websocket loop: {e}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        manager.disconnect(connection_id)


@router.websocket("/connect/auth")
async def websocket_endpoint_auth(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    topics: str = Query("", description="Comma-separated topics to subscribe"),
):
    """
    Authenticated WebSocket connection endpoint.
    Requires JWT token for access.
    """
    connection_id = str(uuid.uuid4())
    
    try:
        # Verify token and get user
        user = await get_current_user(token)
        
        await manager.connect(websocket, connection_id)
        
        # Subscribe to requested topics
        if topics:
            topic_list = [t.strip() for t in topics.split(",") if t.strip()]
            for topic in topic_list:
                manager.subscribe(connection_id, topic)
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "user": user["username"],
            "topics": topic_list if topics else []
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    logger.info(f"Received message from {connection_id}: {data}")
                    # Try to parse JSON message (subscribe/unsubscribe)
                    try:
                        import json
                        msg = json.loads(data)
                        if msg.get("type") == "subscribe" and "topics" in msg:
                            # Subscribe to additional topics
                            for topic in msg["topics"]:
                                if topic in [Topics.KITCHEN, Topics.CASHIER, Topics.TABLES, Topics.ORDERS, Topics.ADMIN, Topics.WAITER, Topics.STOCK]:
                                    manager.subscribe(connection_id, topic)
                        elif msg.get("type") == "unsubscribe" and "topics" in msg:
                            # Unsubscribe from topics
                            for topic in msg["topics"]:
                                manager.unsubscribe(connection_id, topic)
                    except (json.JSONDecodeError, KeyError):
                        # Not a JSON message or doesn't have expected structure, ignore
                        pass
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in websocket loop: {e}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": "Authentication failed"})
    finally:
        manager.disconnect(connection_id)


# Broadcast endpoints for internal use
@router.post("/broadcast/{topic}")
async def broadcast_to_topic(topic: str, message: dict):
    """
    Broadcast message to all subscribers of a topic.
    Note: Should be protected in production.
    """
    await manager.broadcast(message, topic=topic)
    return {"success": True}


@router.post("/broadcast")
async def broadcast_to_all(message: dict):
    """
    Broadcast message to all connected clients.
    Note: Should be protected in production.
    """
    await manager.broadcast(message, topic=None)
    return {"success": True}


