"""add production indexes

Revision ID: 2025_01_20_0000
Revises: 2025_01_15_0000
Create Date: 2025-01-20 00:00:00.000000

Production için kritik performans index'leri
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2025_01_20_0000'
down_revision = '2025_01_15_0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Production için kritik index'leri ekle"""
    
    # API keys için index (sık kullanılan sorgu)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_api_key 
        ON api_keys (api_key)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_isletme_aktif 
        ON api_keys (isletme_id, aktif)
    """)
    
    # Users için index (tenant_id ile sorgu)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_tenant_aktif 
        ON users (tenant_id, aktif)
        WHERE tenant_id IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_username 
        ON users (username)
    """)
    
    # Subeler için index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_subeler_isletme_aktif 
        ON subeler (isletme_id, aktif)
    """)
    
    # Menu varyasyonlar için index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_menu_varyasyonlar_menu_aktif 
        ON menu_varyasyonlar (menu_id, aktif)
    """)
    
    # Adisyonlar için index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_adisyons_sube_masa_durum 
        ON adisyons (sube_id, masa, durum)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_adisyons_durum_acik 
        ON adisyons (durum) 
        WHERE durum = 'acik'
    """)
    
    # Siparisler için ek index'ler
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_siparisler_sube_durum 
        ON siparisler (sube_id, durum)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_siparisler_created_at_desc 
        ON siparisler (created_at DESC)
    """)
    
    # Odemeler için ek index'ler
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_odemeler_sube_created_at 
        ON odemeler (sube_id, created_at DESC)
    """)
    
    # API usage logs için index (analytics için)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_logs_isletme_created 
        ON api_usage_logs (isletme_id, created_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_logs_api_key_created 
        ON api_usage_logs (api_key_id, created_at DESC)
        WHERE api_key_id IS NOT NULL
    """)


def downgrade() -> None:
    """Index'leri kaldır"""
    op.execute("DROP INDEX IF EXISTS idx_api_usage_logs_api_key_created")
    op.execute("DROP INDEX IF EXISTS idx_api_usage_logs_isletme_created")
    op.execute("DROP INDEX IF EXISTS idx_odemeler_sube_created_at")
    op.execute("DROP INDEX IF EXISTS idx_siparisler_created_at_desc")
    op.execute("DROP INDEX IF EXISTS idx_siparisler_sube_durum")
    op.execute("DROP INDEX IF EXISTS idx_adisyons_durum_acik")
    op.execute("DROP INDEX IF EXISTS idx_adisyons_sube_masa_durum")
    op.execute("DROP INDEX IF EXISTS idx_menu_varyasyonlar_menu_aktif")
    op.execute("DROP INDEX IF EXISTS idx_subeler_isletme_aktif")
    op.execute("DROP INDEX IF EXISTS idx_users_username")
    op.execute("DROP INDEX IF EXISTS idx_users_tenant_aktif")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_isletme_aktif")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_api_key")

