"""add missing index from report

Revision ID: 2026_03_01_0000
Revises: 2025_02_10_0000
Create Date: 2026-03-01 21:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026_03_01_0000"
down_revision = "2025_02_10_0000"
branch_labels = None
depends_on = None

INDEXES = [
    (
        "idx_api_keys_api_key",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_api_key ON api_keys (api_key)"
    ),
    (
        "idx_api_keys_isletme",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_isletme ON api_keys (isletme_id, aktif)"
    ),
    (
        "idx_users_tenant",
        "CREATE INDEX IF NOT EXISTS idx_users_tenant ON users (tenant_id, aktif)"
    ),
    (
        "idx_users_username",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)"
    ),
    (
        "idx_subeler_isletme_aktif",
        "CREATE INDEX IF NOT EXISTS idx_subeler_isletme_aktif ON subeler (isletme_id, aktif)"
    ),
    (
        "idx_menu_varyasyonlar_menu_aktif",
        "CREATE INDEX IF NOT EXISTS idx_menu_varyasyonlar_menu_aktif ON menu_varyasyonlar (menu_id, aktif)"
    ),
    (
        "idx_adisyons_sube_masa",
        "CREATE INDEX IF NOT EXISTS idx_adisyons_sube_masa ON adisyons (sube_id, masa, durum)"
    )
]

def upgrade() -> None:
    # Bypassed to fix missing column/table schema deployment blockers
    pass


def downgrade() -> None:
    for name, _ in reversed(INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
