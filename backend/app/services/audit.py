# backend/app/services/audit.py
"""
Audit Log Servisi
Kritik işlemlerin loglanması ve görüntülenmesi
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging

from ..db.database import db

logger = logging.getLogger(__name__)


class AuditService:
    """Audit log işlemlerini yöneten servis"""

    @staticmethod
    async def log_action(
        action: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        sube_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> int:
        """
        Bir işlemi audit log'a kaydet

        Args:
            action: İşlem türü (örn: "menu.create", "siparis.update", "odeme.delete")
            user_id: Kullanıcı ID
            username: Kullanıcı adı
            sube_id: Şube ID
            entity_type: Etkilenen varlık tipi (örn: "menu", "siparis", "stok")
            entity_id: Etkilenen varlık ID
            old_values: Eski değerler (güncelleme için)
            new_values: Yeni değerler
            ip_address: Kullanıcının IP adresi
            user_agent: Kullanıcının tarayıcı bilgisi
            success: İşlem başarılı mı?
            error_message: Hata mesajı (varsa)

        Returns:
            Oluşturulan audit log ID
        """
        try:
            # JSON serialize (None değerleri temizle)
            old_json = json.dumps(old_values) if old_values else None
            new_json = json.dumps(new_values) if new_values else None

            query = """
                INSERT INTO audit_logs (
                    action, user_id, username, sube_id,
                    entity_type, entity_id, old_values, new_values,
                    ip_address, user_agent, success, error_message
                )
                VALUES (
                    :action, :user_id, :username, :sube_id,
                    :entity_type, :entity_id, :old_values, :new_values,
                    :ip_address, :user_agent, :success, :error_message
                )
                RETURNING id
            """

            row = await db.fetch_one(
                query,
                {
                    "action": action,
                    "user_id": user_id,
                    "username": username,
                    "sube_id": sube_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "old_values": old_json,
                    "new_values": new_json,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "success": success,
                    "error_message": error_message,
                },
            )

            log_id = row["id"]
            logger.info(f"Audit log created: {action} by {username} (ID: {log_id})")
            return log_id

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            # Audit log hatası uygulamayı durdurmamalı
            return -1

    @staticmethod
    async def get_logs(
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        sube_id: Optional[int] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Audit log'ları filtrele ve getir

        Args:
            limit: Maksimum kayıt sayısı
            offset: Sayfa kaydırma
            user_id: Kullanıcı ID filtresi
            username: Kullanıcı adı filtresi
            sube_id: Şube filtresi
            action: İşlem türü filtresi
            entity_type: Varlık tipi filtresi
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi
            success_only: Sadece başarılı işlemler

        Returns:
            Audit log kayıtları listesi
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id is not None:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id

        if username is not None:
            conditions.append("username = :username")
            params["username"] = username

        if sube_id is not None:
            conditions.append("sube_id = :sube_id")
            params["sube_id"] = sube_id

        if action is not None:
            conditions.append("action ILIKE :action")
            params["action"] = f"%{action}%"

        if entity_type is not None:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type

        if start_date is not None:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date

        if end_date is not None:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        if success_only is not None:
            conditions.append("success = :success")
            params["success"] = success_only

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                id, action, user_id, username, sube_id,
                entity_type, entity_id, old_values, new_values,
                ip_address, user_agent, success, error_message,
                created_at
            FROM audit_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = await db.fetch_all(query, params)

        return [
            {
                "id": row["id"],
                "action": row["action"],
                "user_id": row["user_id"],
                "username": row["username"],
                "sube_id": row["sube_id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "old_values": json.loads(row["old_values"]) if row["old_values"] else None,
                "new_values": json.loads(row["new_values"]) if row["new_values"] else None,
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "success": row["success"],
                "error_message": row["error_message"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    @staticmethod
    async def get_statistics(
        sube_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Audit log istatistiklerini getir

        Returns:
            İstatistik bilgileri (toplam işlem, başarılı, başarısız, kullanıcı başına dağılım vb.)
        """
        conditions = []
        params: Dict[str, Any] = {}

        if sube_id is not None:
            conditions.append("sube_id = :sube_id")
            params["sube_id"] = sube_id

        if start_date is not None:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date

        if end_date is not None:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Toplam işlem sayısı
        query_total = f"SELECT COUNT(*) as total FROM audit_logs WHERE {where_clause}"
        total_row = await db.fetch_one(query_total, params)

        # Başarılı/başarısız işlem sayısı
        query_success = f"""
            SELECT
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed
            FROM audit_logs
            WHERE {where_clause}
        """
        success_row = await db.fetch_one(query_success, params)

        # En aktif kullanıcılar
        query_top_users = f"""
            SELECT username, COUNT(*) as action_count
            FROM audit_logs
            WHERE {where_clause} AND username IS NOT NULL
            GROUP BY username
            ORDER BY action_count DESC
            LIMIT 10
        """
        top_users = await db.fetch_all(query_top_users, params)

        # En çok yapılan işlemler
        query_top_actions = f"""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE {where_clause}
            GROUP BY action
            ORDER BY count DESC
            LIMIT 10
        """
        top_actions = await db.fetch_all(query_top_actions, params)

        return {
            "total_actions": total_row["total"] if total_row else 0,
            "successful_actions": success_row["successful"] if success_row else 0,
            "failed_actions": success_row["failed"] if success_row else 0,
            "top_users": [
                {"username": row["username"], "action_count": row["action_count"]}
                for row in top_users
            ],
            "top_actions": [
                {"action": row["action"], "count": row["count"]}
                for row in top_actions
            ],
        }


# Global audit service instance
audit_service = AuditService()
