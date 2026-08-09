"""add_user_tokens

Revision ID: b8f2a9c3d1e5
Revises: 3fa44eb8f03c
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision: str = 'b8f2a9c3d1e5'
down_revision: str = '3fa44eb8f03c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('token_family', sa.UUID(), nullable=False),
        sa.Column('token_type', sa.String(length=30), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_user_tokens_token_hash'),
    )
    op.create_index('ix_user_tokens_user_id', 'user_tokens', ['user_id'])
    op.create_index('ix_user_tokens_token_hash', 'user_tokens', ['token_hash'])
    op.create_index('ix_user_tokens_token_family', 'user_tokens', ['token_family'])
    op.create_index('ix_user_tokens_user_id_type', 'user_tokens', ['user_id', 'token_type'])
    op.create_index('ix_user_tokens_token_type', 'user_tokens', ['token_type'])
    op.create_index('ix_user_tokens_expires_at', 'user_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_user_tokens_expires_at', 'user_tokens')
    op.drop_index('ix_user_tokens_token_type', 'user_tokens')
    op.drop_index('ix_user_tokens_user_id_type', 'user_tokens')
    op.drop_index('ix_user_tokens_token_family', 'user_tokens')
    op.drop_index('ix_user_tokens_token_hash', 'user_tokens')
    op.drop_index('ix_user_tokens_user_id', 'user_tokens')
    op.drop_table('user_tokens')
