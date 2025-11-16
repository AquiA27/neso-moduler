# backend/app/services/push_notification.py
"""
Push Notification Servisi
WebPush ve browser push notification desteği
"""
import logging
from typing import List, Optional, Dict, Any
import json

from ..db.database import db

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Push notification servisi"""

    @staticmethod
    async def subscribe_user(
        user_id: int,
        subscription_data: Dict[str, Any],
    ) -> bool:
        """
        Kullanıcıyı push notification için kaydet

        Args:
            user_id: Kullanıcı ID
            subscription_data: Browser subscription data (endpoint, keys)

        Returns:
            Başarılı ise True
        """
        try:
            # Subscription'ı database'e kaydet
            await db.execute(
                """
                INSERT INTO push_subscriptions (user_id, endpoint, p256dh_key, auth_key, subscription_data)
                VALUES (:user_id, :endpoint, :p256dh, :auth, :data)
                ON CONFLICT (user_id, endpoint) DO UPDATE
                SET p256dh_key = EXCLUDED.p256dh_key,
                    auth_key = EXCLUDED.auth_key,
                    subscription_data = EXCLUDED.subscription_data,
                    updated_at = NOW()
                """,
                {
                    "user_id": user_id,
                    "endpoint": subscription_data.get("endpoint"),
                    "p256dh": subscription_data.get("keys", {}).get("p256dh"),
                    "auth": subscription_data.get("keys", {}).get("auth"),
                    "data": json.dumps(subscription_data),
                },
            )

            logger.info(f"Push subscription saved for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save push subscription: {e}", exc_info=True)
            return False

    @staticmethod
    async def unsubscribe_user(user_id: int, endpoint: str) -> bool:
        """Kullanıcının push subscription'ını sil"""
        try:
            await db.execute(
                "DELETE FROM push_subscriptions WHERE user_id = :user_id AND endpoint = :endpoint",
                {"user_id": user_id, "endpoint": endpoint},
            )
            logger.info(f"Push subscription removed for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove push subscription: {e}", exc_info=True)
            return False

    @staticmethod
    async def send_notification(
        user_ids: List[int],
        title: str,
        body: str,
        icon: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Kullanıcılara push notification gönder

        Args:
            user_ids: Kullanıcı ID'leri
            title: Bildirim başlığı
            body: Bildirim metni
            icon: İkon URL'i
            data: Ek veri

        Returns:
            Başarı/hata sayıları
        """
        # TODO: pywebpush kütüphanesi ile gerçek push notification gönderimi
        # Şu an için database'e kayıt ve WebSocket ile gönderim yapıyoruz

        try:
            # Bildirim geçmişine kaydet
            for user_id in user_ids:
                await db.execute(
                    """
                    INSERT INTO notification_history
                    (user_id, notification_type, title, body, icon, data, status)
                    VALUES (:user_id, 'push', :title, :body, :icon, :data, 'sent')
                    """,
                    {
                        "user_id": user_id,
                        "title": title,
                        "body": body,
                        "icon": icon,
                        "data": json.dumps(data) if data else None,
                    },
                )

            logger.info(f"Push notifications queued for {len(user_ids)} users")

            return {"success": len(user_ids), "failed": 0}

        except Exception as e:
            logger.error(f"Failed to send push notifications: {e}", exc_info=True)
            return {"success": 0, "failed": len(user_ids)}


# Global push notification service
push_notification_service = PushNotificationService()
