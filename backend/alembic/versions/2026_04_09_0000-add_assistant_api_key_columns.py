"""add assistant api key columns to tenant_customizations

Revision ID: 2026_04_09_0000
Revises: 2026_03_01_0000
Create Date: 2026-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026_04_09_0000"
down_revision = "2026_03_01_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_customizations
            ADD COLUMN IF NOT EXISTS openai_api_key TEXT,
            ADD COLUMN IF NOT EXISTS openai_model TEXT DEFAULT 'gpt-4o',
            ADD COLUMN IF NOT EXISTS customer_assistant_openai_api_key TEXT,
            ADD COLUMN IF NOT EXISTS customer_assistant_openai_model TEXT DEFAULT 'gpt-4o',
            ADD COLUMN IF NOT EXISTS customer_assistant_tts_voice_id TEXT,
            ADD COLUMN IF NOT EXISTS customer_assistant_tts_speech_rate NUMERIC(3,2) DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS customer_assistant_tts_provider TEXT DEFAULT 'system',
            ADD COLUMN IF NOT EXISTS business_assistant_openai_api_key TEXT,
            ADD COLUMN IF NOT EXISTS business_assistant_openai_model TEXT DEFAULT 'gpt-4o',
            ADD COLUMN IF NOT EXISTS business_assistant_tts_voice_id TEXT,
            ADD COLUMN IF NOT EXISTS business_assistant_tts_speech_rate NUMERIC(3,2) DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS business_assistant_tts_provider TEXT DEFAULT 'system'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_customizations
            DROP COLUMN IF EXISTS customer_assistant_openai_api_key,
            DROP COLUMN IF EXISTS customer_assistant_openai_model,
            DROP COLUMN IF EXISTS customer_assistant_tts_voice_id,
            DROP COLUMN IF EXISTS customer_assistant_tts_speech_rate,
            DROP COLUMN IF EXISTS customer_assistant_tts_provider,
            DROP COLUMN IF EXISTS business_assistant_openai_api_key,
            DROP COLUMN IF EXISTS business_assistant_openai_model,
            DROP COLUMN IF EXISTS business_assistant_tts_voice_id,
            DROP COLUMN IF EXISTS business_assistant_tts_speech_rate,
            DROP COLUMN IF EXISTS business_assistant_tts_provider
    """)
