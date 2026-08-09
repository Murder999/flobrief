"""add brief templates

Revision ID: d2e3f4a5b6c7
Revises: c1e2f3a4b5d6
Create Date: 2026-07-08
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1e2f3a4b5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brief_template_industries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_industry_code", "brief_template_industries", ["code"])

    op.create_table(
        "brief_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("is_system_template", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_brief_template_agency_id", "brief_templates", ["agency_id"])
    op.create_index("ix_brief_template_industry", "brief_templates", ["industry"])

    op.create_table(
        "brief_template_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brief_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_section_template_id", "brief_template_sections", ["template_id"])

    op.create_table(
        "brief_template_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brief_template_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("help_text", sa.Text, nullable=True),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("options", postgresql.JSONB, nullable=True),
        sa.Column("validation_rules", postgresql.JSONB, nullable=True),
        sa.Column("placeholder", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_field_section_id", "brief_template_fields", ["section_id"])
    op.create_unique_constraint("uq_field_key_per_section", "brief_template_fields", ["section_id", "field_key"])

    # Seed initial industries
    industries = op.get_bind()
    industries.execute(
        sa.text("""
        INSERT INTO brief_template_industries (id, code, name, description, is_active, created_at, updated_at)
        VALUES
          (gen_random_uuid(), 'social_media',      'Sosyal Medya',          'Instagram, TikTok, LinkedIn, X kampanyaları', true, now(), now()),
          (gen_random_uuid(), 'pr',                'Halkla İlişkiler',      'Basın bülteni, medya ilişkileri, kriz iletişimi', true, now(), now()),
          (gen_random_uuid(), 'event',             'Etkinlik',              'Lansman, fuar, sahne etkinlikleri', true, now(), now()),
          (gen_random_uuid(), 'digital_ad',        'Dijital Reklam',        'Google, Meta, display ve programatik reklamlar', true, now(), now()),
          (gen_random_uuid(), 'influencer',        'Influencer Marketing',  'Influencer işbirliği ve içerik üretimi', true, now(), now()),
          (gen_random_uuid(), 'branding',          'Marka Kimliği',         'Logo, kurumsal kimlik, marka rehberi', true, now(), now()),
          (gen_random_uuid(), 'content',           'İçerik Pazarlama',      'Blog, video, podcast içerik stratejisi', true, now(), now()),
          (gen_random_uuid(), 'email_marketing',   'E-posta Pazarlama',     'Kampanya, otomasyon, newsletter', true, now(), now()),
          (gen_random_uuid(), 'photography',       'Fotoğraf & Video',      'Ürün, kurumsal ve kampanya çekimleri', true, now(), now()),
          (gen_random_uuid(), 'web',               'Web & Dijital',         'Website, landing page, UX/UI tasarımı', true, now(), now())
        """)
    )


def downgrade() -> None:
    op.drop_table("brief_template_fields")
    op.drop_table("brief_template_sections")
    op.drop_table("brief_templates")
    op.drop_table("brief_template_industries")
