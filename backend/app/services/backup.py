# backend/app/services/backup.py
"""
Yedekleme Servisi
PostgreSQL veritabanını otomatik yedekleme ve restore
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess

from ..core.config import settings
from ..db.database import db

logger = logging.getLogger(__name__)


class BackupService:
    """Veritabanı yedekleme servisi"""

    def __init__(self):
        self.backup_dir = Path(settings.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(self, backup_type: str = "full", created_by: str = "system") -> Dict[str, Any]:
        """
        Veritabanı yedeği oluştur

        Args:
            backup_type: 'full' veya 'incremental'
            created_by: Yedeği oluşturan kullanıcı/sistem

        Returns:
            Yedekleme bilgileri
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"neso_backup_{backup_type}_{timestamp}.sql"
        file_path = self.backup_dir / filename

        # Backup history'ye başlangıç kaydı
        backup_record = await db.fetch_one(
            """
            INSERT INTO backup_history
            (backup_type, file_path, status, created_by, started_at)
            VALUES (:backup_type, :file_path, 'in_progress', :created_by, NOW())
            RETURNING id
            """,
            {
                "backup_type": backup_type,
                "file_path": str(file_path),
                "created_by": created_by,
            },
        )
        backup_id = backup_record["id"]

        try:
            # DATABASE_URL'den connection bilgilerini parse et
            # Format: postgresql+asyncpg://user:pass@host:port/dbname
            db_url = settings.DATABASE_URL
            if "asyncpg://" in db_url:
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            elif "postgresql+asyncpg://" in db_url:
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            # Parse connection string
            from urllib.parse import urlparse
            parsed = urlparse(db_url)

            # pg_dump komutu ile yedekleme
            pg_dump_cmd = [
                "pg_dump",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/") if parsed.path else "neso",
                "-F", "p",  # Plain text SQL format
                "-f", str(file_path),
                "--no-owner",  # Owner bilgisi olmadan
                "--no-acl",    # ACL bilgisi olmadan
            ]

            # Password environment variable
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            logger.info(f"Starting backup: {filename}")

            # Subprocess ile pg_dump çalıştır
            process = await asyncio.create_subprocess_exec(
                *pg_dump_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Backup failed: {error_msg}")

                # Backup history'ye hata kaydı
                await db.execute(
                    """
                    UPDATE backup_history
                    SET status = 'failed', error_message = :error, completed_at = NOW()
                    WHERE id = :id
                    """,
                    {"id": backup_id, "error": error_msg},
                )

                return {
                    "success": False,
                    "backup_id": backup_id,
                    "error": error_msg,
                }

            # Dosya boyutu
            file_size = file_path.stat().st_size

            # Backup history güncelle
            await db.execute(
                """
                UPDATE backup_history
                SET status = 'success', file_size_bytes = :size, completed_at = NOW()
                WHERE id = :id
                """,
                {"id": backup_id, "size": file_size},
            )

            logger.info(f"Backup completed: {filename} ({file_size} bytes)")

            # Eski yedekleri temizle
            await self._cleanup_old_backups()

            return {
                "success": True,
                "backup_id": backup_id,
                "file_path": str(file_path),
                "file_size": file_size,
                "filename": filename,
            }

        except Exception as e:
            logger.error(f"Backup error: {e}", exc_info=True)

            # Backup history'ye hata kaydı
            await db.execute(
                """
                UPDATE backup_history
                SET status = 'failed', error_message = :error, completed_at = NOW()
                WHERE id = :id
                """,
                {"id": backup_id, "error": str(e)},
            )

            return {
                "success": False,
                "backup_id": backup_id,
                "error": str(e),
            }

    async def _cleanup_old_backups(self) -> None:
        """Eski yedekleri sil (retention policy)"""
        try:
            retention_days = settings.BACKUP_RETENTION_DAYS
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # Eski backup kayıtlarını al
            old_backups = await db.fetch_all(
                """
                SELECT id, file_path
                FROM backup_history
                WHERE started_at < :cutoff AND status = 'success'
                """,
                {"cutoff": cutoff_date},
            )

            for backup in old_backups:
                # Dosyayı sil
                file_path = Path(backup["file_path"])
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted old backup: {file_path.name}")

                # Kaydı sil
                await db.execute(
                    "DELETE FROM backup_history WHERE id = :id",
                    {"id": backup["id"]},
                )

        except Exception as e:
            logger.warning(f"Cleanup old backups error: {e}")

    async def get_backup_history(
        self, limit: int = 100, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Yedekleme geçmişini getir

        Args:
            limit: Maksimum kayıt sayısı
            status: Durum filtresi ('success', 'failed', 'in_progress')

        Returns:
            Yedekleme kayıtları
        """
        query = """
            SELECT
                id, backup_type, file_path, file_size_bytes,
                status, error_message, started_at, completed_at, created_by
            FROM backup_history
        """

        params: Dict[str, Any] = {"limit": limit}

        if status:
            query += " WHERE status = :status"
            params["status"] = status

        query += " ORDER BY started_at DESC LIMIT :limit"

        rows = await db.fetch_all(query, params)

        return [
            {
                "id": row["id"],
                "backup_type": row["backup_type"],
                "file_path": row["file_path"],
                "file_size_bytes": row["file_size_bytes"],
                "file_size_mb": round(row["file_size_bytes"] / (1024 * 1024), 2) if row["file_size_bytes"] else None,
                "status": row["status"],
                "error_message": row["error_message"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "created_by": row["created_by"],
                "duration_seconds": (
                    (row["completed_at"] - row["started_at"]).total_seconds()
                    if row["started_at"] and row["completed_at"]
                    else None
                ),
            }
            for row in rows
        ]

    async def restore_backup(self, backup_id: int) -> Dict[str, Any]:
        """
        Yedekten geri yükle (DANGEROUS!)

        Args:
            backup_id: Yedekleme ID

        Returns:
            Restore sonucu
        """
        # Backup kaydını al
        backup = await db.fetch_one(
            "SELECT * FROM backup_history WHERE id = :id AND status = 'success'",
            {"id": backup_id},
        )

        if not backup:
            return {"success": False, "error": "Backup not found or invalid"}

        file_path = Path(backup["file_path"])
        if not file_path.exists():
            return {"success": False, "error": "Backup file not found"}

        try:
            # DATABASE_URL parse
            db_url = settings.DATABASE_URL
            from urllib.parse import urlparse
            parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

            # psql komutu ile restore
            psql_cmd = [
                "psql",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/") if parsed.path else "neso",
                "-f", str(file_path),
            ]

            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            logger.warning(f"RESTORING DATABASE from backup: {file_path.name}")

            process = await asyncio.create_subprocess_exec(
                *psql_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Restore failed: {error_msg}")
                return {"success": False, "error": error_msg}

            logger.info(f"Restore completed: {file_path.name}")

            return {
                "success": True,
                "backup_id": backup_id,
                "restored_from": str(file_path),
            }

        except Exception as e:
            logger.error(f"Restore error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# Global backup service instance
backup_service = BackupService()
