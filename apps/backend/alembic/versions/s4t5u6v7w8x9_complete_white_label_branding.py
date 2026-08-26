"""complete white-label branding, assets and domain uniqueness

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-08-10 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("background_color", "surface_color", "text_color", "border_color"):
        op.add_column("agency_branding_settings", sa.Column(name, sa.String(7), nullable=True))
    for name in ("support_email", "footer_company_name"):
        op.add_column("agency_branding_settings", sa.Column(name, sa.String(255), nullable=True))
    op.add_column(
        "agency_branding_settings", sa.Column("support_phone", sa.String(50), nullable=True)
    )
    for name in ("website_url", "copyright_text"):
        op.add_column("agency_branding_settings", sa.Column(name, sa.String(500), nullable=True))
    for name in ("dark_logo_asset_id", "og_image_asset_id"):
        op.add_column(
            "agency_branding_settings",
            sa.Column(name, sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            f"fk_agency_branding_{name}",
            "agency_branding_settings",
            "assets",
            [name],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column(
        "platform_branding_defaults", sa.Column("secondary_color", sa.String(7), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("border_color", sa.String(7), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults",
        sa.Column("og_image_storage_key", sa.String(500), nullable=True),
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("og_image_mime_type", sa.String(127), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("support_phone", sa.String(50), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("website_url", sa.String(500), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults",
        sa.Column("footer_company_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("copyright_text", sa.String(500), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("public_title", sa.String(200), nullable=True)
    )
    op.add_column(
        "platform_branding_defaults", sa.Column("public_description", sa.String(500), nullable=True)
    )

    op.create_unique_constraint("uq_domain_hostname", "custom_domain_settings", ["domain"])
    op.execute(
        sa.text(
            """
            UPDATE platform_branding_defaults SET
              portal_name = COALESCE(portal_name, 'PostPiloter'),
              login_title = COALESCE(login_title, 'PostPiloter''a Giriş Yap'),
              primary_color = COALESCE(primary_color, '#4F46E5'),
              secondary_color = COALESCE(secondary_color, '#7C3AED'),
              accent_color = COALESCE(accent_color, '#6366F1'),
              background_color = COALESCE(background_color, '#FAF9F7'),
              surface_color = COALESCE(surface_color, '#FFFFFF'),
              text_color = COALESCE(text_color, '#1A1917'),
              border_color = COALESCE(border_color, '#E5E2DC'),
              link_color = COALESCE(link_color, '#4338CA'),
              email_from_name = COALESCE(email_from_name, 'PostPiloter'),
              support_email = COALESCE(support_email, 'support@postpiloter.com'),
              website_url = COALESCE(website_url, 'https://postpiloter.com'),
              footer_company_name = COALESCE(footer_company_name, 'PostPiloter'),
              copyright_text = COALESCE(copyright_text, 'PostPiloter. Tüm hakları saklıdır.'),
              terms_url = COALESCE(terms_url, 'https://postpiloter.com/terms'),
              privacy_url = COALESCE(privacy_url, 'https://postpiloter.com/privacy')
            WHERE deleted_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("uq_domain_hostname", "custom_domain_settings", type_="unique")
    for name in (
        "public_description",
        "public_title",
        "copyright_text",
        "footer_company_name",
        "website_url",
        "support_phone",
        "og_image_mime_type",
        "og_image_storage_key",
        "border_color",
        "secondary_color",
    ):
        op.drop_column("platform_branding_defaults", name)
    for name in ("og_image_asset_id", "dark_logo_asset_id"):
        op.drop_constraint(
            f"fk_agency_branding_{name}", "agency_branding_settings", type_="foreignkey"
        )
        op.drop_column("agency_branding_settings", name)
    for name in (
        "copyright_text",
        "website_url",
        "support_phone",
        "footer_company_name",
        "support_email",
        "border_color",
        "text_color",
        "surface_color",
        "background_color",
    ):
        op.drop_column("agency_branding_settings", name)
