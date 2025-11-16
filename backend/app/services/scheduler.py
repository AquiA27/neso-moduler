# backend/app/services/scheduler.py
"""
Zamanlayıcı Servisi
APScheduler ile otomatik görevler (backup, cleanup, vb.)
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.config import settings
from .backup import backup_service

logger = logging.getLogger(__name__)


class SchedulerService:
    """Zamanlayıcı servisi"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_started = False

    def start(self):
        """Scheduler'ı başlat"""
        if self._is_started:
            logger.warning("Scheduler already started")
            return

        if not settings.BACKUP_ENABLED:
            logger.info("Backup scheduling disabled in settings")
            return

        # Otomatik yedekleme görevini ekle
        try:
            # Cron formatı: "minute hour day month day_of_week"
            # Varsayılan: "0 2 * * *" = Her gün saat 02:00
            self.scheduler.add_job(
                self._auto_backup,
                CronTrigger.from_crontab(settings.BACKUP_SCHEDULE_CRON),
                id="auto_backup",
                name="Otomatik Veritabanı Yedekleme",
                replace_existing=True,
            )
            logger.info(
                f"Scheduled auto backup: {settings.BACKUP_SCHEDULE_CRON}"
            )
        except Exception as e:
            logger.error(f"Failed to schedule backup job: {e}")

        # Scheduler'ı başlat
        self.scheduler.start()
        self._is_started = True
        logger.info("Scheduler started successfully")

    def shutdown(self):
        """Scheduler'ı kapat"""
        if self._is_started:
            self.scheduler.shutdown()
            self._is_started = False
            logger.info("Scheduler shutdown")

    async def _auto_backup(self):
        """Otomatik yedekleme görevi"""
        logger.info("Starting scheduled auto backup...")
        try:
            result = await backup_service.create_backup(
                backup_type="full",
                created_by="scheduler",
            )

            if result["success"]:
                logger.info(
                    f"Auto backup completed: {result.get('filename')}"
                )
            else:
                logger.error(
                    f"Auto backup failed: {result.get('error')}"
                )

        except Exception as e:
            logger.error(f"Auto backup error: {e}", exc_info=True)


# Global scheduler instance
scheduler_service = SchedulerService()
