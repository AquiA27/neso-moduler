"""add pgvector and menu embeddings

Revision ID: 2025_01_15_0000
Revises: 2025_01_02_0000
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_01_15_0000'
down_revision = '2025_01_02_0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 2. Create menu_embeddings table
    op.create_table(
        'menu_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('menu_id', sa.Integer(), nullable=False),
        sa.Column('sube_id', sa.Integer(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create foreign key to menu table
    op.create_foreign_key(
        'fk_menu_embeddings_menu_id',
        'menu_embeddings', 'menu',
        ['menu_id'], ['id'],
        ondelete='CASCADE'
    )

    # 4. Create indexes for fast retrieval
    op.create_index(
        'idx_menu_embeddings_sube_id',
        'menu_embeddings',
        ['sube_id']
    )

    op.create_index(
        'idx_menu_embeddings_menu_id',
        'menu_embeddings',
        ['menu_id']
    )

    # Note: Vector similarity index will be created after embeddings are populated
    # This is because IVFFlat index requires data for clustering
    # Run this SQL manually after populating embeddings:
    # CREATE INDEX menu_embeddings_vector_idx ON menu_embeddings
    # USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


def downgrade() -> None:
    op.drop_index('idx_menu_embeddings_menu_id', table_name='menu_embeddings')
    op.drop_index('idx_menu_embeddings_sube_id', table_name='menu_embeddings')
    op.drop_constraint('fk_menu_embeddings_menu_id', 'menu_embeddings', type_='foreignkey')
    op.drop_table('menu_embeddings')
    op.execute('DROP EXTENSION IF EXISTS vector')
