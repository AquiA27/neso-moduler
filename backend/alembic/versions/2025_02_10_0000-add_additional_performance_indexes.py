"""add additional performance indexes

Revision ID: 2025_02_10_0000
Revises: 2025_01_20_0000
Create Date: 2026-02-09 09:30:00.000000

Bu migration tenant bazlÄ± raporlama ve stok operasyonlarÄ± iÃ§in eksik index'leri ekler.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2025_02_10_0000"
down_revision = "2025_01_20_0000"
branch_labels = None
depends_on = None


INDEXES = [
    (
        "idx_recete_sube_urun",
        """
        CREATE INDEX IF NOT EXISTS idx_recete_sube_urun
        ON receteler (sube_id, urun)
        """,
    ),
    (
        "idx_stok_sube_ad",
        """
        CREATE INDEX IF NOT EXISTS idx_stok_sube_ad
        ON stok_kalemleri (sube_id, ad)
        """,
    ),
    (
        "idx_masalar_sube_durum",
        """
        CREATE INDEX IF NOT EXISTS idx_masalar_sube_durum
        ON masalar (sube_id, durum)
        """,
    ),
    (
        "idx_user_permissions_username",
        """
        CREATE INDEX IF NOT EXISTS idx_user_permissions_username
        ON user_permissions (username)
        """,
    ),
    (
        "idx_siparisler_tenant_time",
        """
        CREATE INDEX IF NOT EXISTS idx_siparisler_tenant_time
        ON siparisler (tenant_id, created_at DESC)
        """,
    ),
    (
        "idx_odemeler_tenant_time",
        """
        CREATE INDEX IF NOT EXISTS idx_odemeler_tenant_time
        ON odemeler (tenant_id, created_at DESC)
        """,
    ),
    (
        "idx_giderler_tenant_time",
        """
        CREATE INDEX IF NOT EXISTS idx_giderler_tenant_time
        ON giderler (tenant_id, tarih DESC)
        """,
    ),
    (
        "idx_siparisler_sube_durum_open",
        """
        CREATE INDEX IF NOT EXISTS idx_siparisler_sube_durum_open
        ON siparisler (sube_id, durum)
        WHERE durum <> 'tamamlandi'
        """,
    ),
    (
        "idx_adisyons_sube_aktif",
        """
        CREATE INDEX IF NOT EXISTS idx_adisyons_sube_aktif
        ON adisyons (sube_id, durum)
        WHERE durum = 'acik'
        """,
    ),
    (
        "idx_menu_tenant_kategori",
        """
        CREATE INDEX IF NOT EXISTS idx_menu_tenant_kategori
        ON menu (tenant_id, kategori)
        """,
    ),
    (
        "idx_menu_tenant_aktif",
        """
        CREATE INDEX IF NOT EXISTS idx_menu_tenant_aktif
        ON menu (tenant_id, aktif)
        WHERE aktif = TRUE
        """,
    ),
    (
        "idx_odemeler_tenant_metod",
        """
        CREATE INDEX IF NOT EXISTS idx_odemeler_tenant_metod
        ON odemeler (tenant_id, odeme_metodu)
        """,
    ),
    (
        "idx_siparisler_urun_time",
        """
        CREATE INDEX IF NOT EXISTS idx_siparisler_urun_time
        ON siparisler (urun, created_at DESC)
        """,
    ),
    (
        "idx_audit_logs_tenant_time",
        """
        CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_time
        ON audit_logs (tenant_id, created_at DESC)
        """,
    ),
    (
        "idx_stok_tenant_kategori",
        """
        CREATE INDEX IF NOT EXISTS idx_stok_tenant_kategori
        ON stok_kalemleri (tenant_id, kategori)
        """,
    ),
    (
        "idx_stok_low_stock",
        """
        CREATE INDEX IF NOT EXISTS idx_stok_low_stock
        ON stok_kalemleri (tenant_id, sube_id)
        WHERE mevcut <= min
        """,
    ),
    (
        "idx_push_subscriptions_tenant_active",
        """
        CREATE INDEX IF NOT EXISTS idx_push_subscriptions_tenant_active
        ON push_subscriptions (tenant_id, is_active)
        WHERE is_active = TRUE
        """,
    ),
    (
        "idx_notification_history_tenant_time",
        """
        CREATE INDEX IF NOT EXISTS idx_notification_history_tenant_time
        ON notification_history (tenant_id, created_at DESC)
        """,
    ),
]


def upgrade() -> None:
    for _, statement in INDEXES:
        op.execute(statement)


def downgrade() -> None:
    for name, _ in reversed(INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
