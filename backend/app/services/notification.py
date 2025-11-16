# backend/app/services/notification.py
"""
Bildirim Servisi
Email, SMS ve diğer bildirim kanalları için merkezi servis
"""
import logging
from typing import List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Bildirim gönderim servisi"""

    @staticmethod
    async def send_email(
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Email gönder

        Args:
            to_emails: Alıcı email listesi
            subject: Email konusu
            body_text: Düz metin gövdesi
            body_html: HTML gövdesi (opsiyonel)

        Returns:
            Başarılı ise True
        """
        # Email ayarları yapılmamışsa gönderme
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured. Skipping email notification.")
            return False

        if not to_emails:
            logger.warning("No email recipients provided.")
            return False

        try:
            # Email mesajı oluştur
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME}>"
            message["To"] = ", ".join(to_emails)

            # Düz metin ve HTML parçalarını ekle
            part1 = MIMEText(body_text, "plain", "utf-8")
            message.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html", "utf-8")
                message.attach(part2)

            # SMTP ile gönder
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                start_tls=True,
            )

            logger.info(f"Email sent successfully to {len(to_emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False

    @staticmethod
    async def send_stock_alert_email(
        stock_name: str,
        alert_type: str,
        current_amount: float,
        min_amount: float,
        unit: str,
        sube_name: str = "Şube",
    ) -> bool:
        """
        Stok uyarısı emaili gönder

        Args:
            stock_name: Stok adı
            alert_type: 'kritik' veya 'tukendi'
            current_amount: Mevcut miktar
            min_amount: Minimum miktar
            unit: Birim
            sube_name: Şube adı

        Returns:
            Başarılı ise True
        """
        # Email alıcıları
        recipients_str = settings.ALERT_EMAIL_RECIPIENTS
        if not recipients_str:
            logger.info("No alert email recipients configured.")
            return False

        # String'i listeye çevir
        recipients = [email.strip() for email in recipients_str.split(",") if email.strip()]
        if not recipients:
            logger.info("No valid email recipients found.")
            return False

        # Email içeriği
        subject = f"⚠️ STOK UYARISI: {stock_name}"

        if alert_type == "tukendi":
            emoji = "🔴"
            status_text = "TÜKENDİ"
            message_text = f"Stok tamamen bitti! Acilen temin edilmesi gerekiyor."
        else:  # kritik
            emoji = "🟡"
            status_text = "KRİTİK SEVİYE"
            message_text = f"Stok kritik seviyeye düştü. En kısa sürede temin edilmeli."

        body_text = f"""
{emoji} STOK UYARISI {emoji}

Stok Adı: {stock_name}
Şube: {sube_name}
Durum: {status_text}

Mevcut Miktar: {current_amount} {unit}
Minimum Miktar: {min_amount} {unit}

{message_text}

---
Bu otomatik bir bildirimdir.
Neso Asistan - Restoran Yönetim Sistemi
        """

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .alert-box {{
            border: 2px solid {"#ef4444" if alert_type == "tukendi" else "#f59e0b"};
            border-radius: 8px;
            padding: 20px;
            background-color: {"#fee2e2" if alert_type == "tukendi" else "#fef3c7"};
        }}
        .alert-title {{
            font-size: 24px;
            font-weight: bold;
            color: {"#dc2626" if alert_type == "tukendi" else "#d97706"};
            margin-bottom: 10px;
        }}
        .stock-info {{ margin: 20px 0; }}
        .stock-row {{ padding: 10px; background-color: white; margin: 5px 0; border-radius: 4px; }}
        .label {{ font-weight: bold; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ccc; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="alert-box">
            <div class="alert-title">{emoji} STOK UYARISI</div>
            <p><strong>Durum:</strong> {status_text}</p>

            <div class="stock-info">
                <div class="stock-row">
                    <span class="label">Stok Adı:</span> {stock_name}
                </div>
                <div class="stock-row">
                    <span class="label">Şube:</span> {sube_name}
                </div>
                <div class="stock-row">
                    <span class="label">Mevcut Miktar:</span> {current_amount} {unit}
                </div>
                <div class="stock-row">
                    <span class="label">Minimum Miktar:</span> {min_amount} {unit}
                </div>
            </div>

            <p style="margin-top: 20px; font-weight: bold;">{message_text}</p>
        </div>

        <div class="footer">
            <p>Bu otomatik bir bildirimdir.</p>
            <p><strong>Neso Asistan</strong> - Restoran Yönetim Sistemi</p>
        </div>
    </div>
</body>
</html>
        """

        return await NotificationService.send_email(
            to_emails=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )


# Global notification service instance
notification_service = NotificationService()
