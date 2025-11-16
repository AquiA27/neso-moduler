# backend/app/websocket/manager.py
"""
WebSocket connection manager for real-time updates.
Manages active connections and broadcasts messages to subscribed clients.
"""
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Subscriptions: {topic: Set[connection_id]}
        self.subscriptions: Dict[str, Set[str]] = {}
        # Connection topics: {connection_id: Set[topic]}
        self.connection_topics: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_topics[connection_id] = set()
        logger.info(f"WebSocket connected: {connection_id}")

    def disconnect(self, connection_id: str):
        """Remove connection and clean up subscriptions"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # Remove from all subscriptions
        if connection_id in self.connection_topics:
            topics = self.connection_topics[connection_id]
            for topic in topics:
                if topic in self.subscriptions:
                    self.subscriptions[topic].discard(connection_id)
            del self.connection_topics[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")

    def subscribe(self, connection_id: str, topic: str):
        """Subscribe connection to a topic"""
        if connection_id not in self.active_connections:
            return False
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
        
        self.subscriptions[topic].add(connection_id)
        
        if connection_id in self.connection_topics:
            self.connection_topics[connection_id].add(topic)
        
        logger.info(f"Subscribed {connection_id} to {topic}")
        return True

    def unsubscribe(self, connection_id: str, topic: str):
        """Unsubscribe connection from a topic"""
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(connection_id)
        
        if connection_id in self.connection_topics:
            self.connection_topics[connection_id].discard(topic)
        
        logger.info(f"Unsubscribed {connection_id} from {topic}")

    async def send_personal_message(self, message: dict, connection_id: str):
        """Send message to a specific connection"""
        if connection_id not in self.active_connections:
            return False
        
        try:
            await self.active_connections[connection_id].send_json(message)
            return True
        except Exception as e:
            logger.error(f"Error sending to {connection_id}: {e}")
            self.disconnect(connection_id)
            return False

    async def broadcast(self, message: dict, topic: str = None):
        """Broadcast message to all subscribers of a topic, or all connections if no topic"""
        if topic:
            # Broadcast to topic subscribers only
            if topic not in self.subscriptions:
                logger.warning(f"Topic '{topic}' has no subscribers")
                return
            
            connection_ids = list(self.subscriptions[topic])
            logger.info(f"Topic '{topic}' has {len(connection_ids)} subscribers: {connection_ids}")
        else:
            # Broadcast to all active connections
            connection_ids = list(self.active_connections.keys())
        
        if not connection_ids:
            logger.warning(f"No connections to broadcast to (topic: {topic})")
            return
        
        # Send to all connections in parallel
        tasks = [
            self.send_personal_message(message, conn_id)
            for conn_id in connection_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Broadcasted to {len(connection_ids)} connections on topic '{topic}'")


# Global manager instance
manager = ConnectionManager()


# Topic constants
class Topics:
    """WebSocket topic names"""
    KITCHEN = "kitchen"  # Mutfak sipariş durumu
    CASHIER = "cashier"  # Kasa işlemleri
    TABLES = "tables"  # Masa durumları
    ORDERS = "orders"  # Tüm sipariş güncellemeleri
    ADMIN = "admin"  # Admin bildirimleri
    WAITER = "waiter"  # Garson çağrıları
    STOCK = "stock"  # Stok uyarıları


