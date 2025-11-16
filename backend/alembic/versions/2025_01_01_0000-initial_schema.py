"""Initial schema with security improvements

Revision ID: initial_schema
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema"""

    # Enable unaccent extension
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # Create isletmeler table
    op.execute("""
        CREATE TABLE IF NOT EXISTS isletmeler (
            id BIGSERIAL PRIMARY KEY,
            ad TEXT NOT NULL,
            vergi_no TEXT,
            telefon TEXT,
            aktif BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create subeler table
    op.execute("""
        CREATE TABLE IF NOT EXISTS subeler (
            id BIGSERIAL PRIMARY KEY,
            isletme_id BIGINT REFERENCES isletmeler(id) ON DELETE CASCADE,
            ad TEXT NOT NULL,
            adres TEXT,
            telefon TEXT,
            aktif BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create users table with improved security
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            sifre_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'operator',
            aktif BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create menu table
    op.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT REFERENCES subeler(id) ON DELETE CASCADE,
            ad TEXT NOT NULL,
            fiyat NUMERIC(10,2) DEFAULT 0,
            kategori TEXT,
            aktif BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create siparisler table
    op.execute("""
        CREATE TABLE IF NOT EXISTS siparisler (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT,
            masa TEXT,
            sepet JSONB,
            durum TEXT DEFAULT 'yeni',
            tutar NUMERIC(10,2) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create odemeler table
    op.execute("""
        CREATE TABLE IF NOT EXISTS odemeler (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT,
            masa TEXT,
            tutar NUMERIC(10,2) NOT NULL,
            yontem TEXT NOT NULL,
            iptal BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create user_sube_izinleri table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_sube_izinleri (
            username TEXT NOT NULL,
            sube_id BIGINT NOT NULL,
            PRIMARY KEY (username, sube_id)
        )
    """)

    # Create app_settings table
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value JSONB,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create stok_kalemleri table
    op.execute("""
        CREATE TABLE IF NOT EXISTS stok_kalemleri (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT NOT NULL,
            kod TEXT NOT NULL,
            ad TEXT,
            birim TEXT,
            miktar NUMERIC(12,3) DEFAULT 0,
            UNIQUE (sube_id, kod)
        )
    """)

    # Create receteler table
    op.execute("""
        CREATE TABLE IF NOT EXISTS receteler (
            id BIGSERIAL PRIMARY KEY,
            sube_id BIGINT NOT NULL,
            urun_norm TEXT NOT NULL,
            kalem_kod TEXT NOT NULL,
            miktar NUMERIC(12,3) NOT NULL
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_created_at ON siparisler (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_durum ON siparisler (durum)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_siparisler_masa ON siparisler (masa)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_menu_sube ON menu (sube_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_odemeler_created_at ON odemeler (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_odemeler_sube ON odemeler (sube_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_recete_sube_urun ON receteler (sube_id, urun_norm)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stok_sube_kod ON stok_kalemleri (sube_id, kod)")

    # Create unique index with unaccent
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_sube_ad_norm
            ON menu (sube_id, unaccent(lower(ad)))
    """)


def downgrade() -> None:
    """Drop all tables"""
    op.execute("DROP TABLE IF EXISTS receteler CASCADE")
    op.execute("DROP TABLE IF EXISTS stok_kalemleri CASCADE")
    op.execute("DROP TABLE IF EXISTS app_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS user_sube_izinleri CASCADE")
    op.execute("DROP TABLE IF EXISTS odemeler CASCADE")
    op.execute("DROP TABLE IF EXISTS siparisler CASCADE")
    op.execute("DROP TABLE IF EXISTS menu CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS subeler CASCADE")
    op.execute("DROP TABLE IF EXISTS isletmeler CASCADE")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
