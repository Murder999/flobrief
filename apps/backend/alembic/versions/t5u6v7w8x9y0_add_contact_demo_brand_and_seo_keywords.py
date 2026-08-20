"""Add contact inbox, demo brand portal user, and SEO keywords.

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t5u6v7w8x9y0"
down_revision: str | None = "s4t5u6v7w8x9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "demo_sandboxes",
        sa.Column("brand_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_demo_sandboxes_brand_user_id_users",
        "demo_sandboxes",
        "users",
        ["brand_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_demo_sandboxes_brand_user_id", "demo_sandboxes", ["brand_user_id"])

    op.add_column("platform_seo_page_settings", sa.Column("keywords", sa.Text(), nullable=True))

    op.create_table(
        "contact_submissions",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_submissions_email", "contact_submissions", ["email"])
    op.create_index("ix_contact_submissions_ip_hash", "contact_submissions", ["ip_hash"])
    op.create_index("ix_contact_submissions_status", "contact_submissions", ["status"])

    op.execute(
        """
        INSERT INTO platform_seo_page_settings
          (id, page_key, title, description, keywords, canonical_url, og_title,
           og_description, og_image_url, twitter_title, twitter_description,
           indexable, follow_links, created_at, updated_at)
        VALUES
          (gen_random_uuid(), 'home',
           'Ajans ve Marka Brief Yönetimi | PostPiloter',
           'Brief, kreatif teslim, görsel revizyon, müşteri onayı ve içerik takvimini tek merkezde yönetin. Ajans ve marka ekipleri için PostPiloter.',
           'ajans yönetim yazılımı, brief yönetim sistemi, müşteri onay platformu, içerik takvimi, kreatif revizyon aracı, marka ajans iş birliği',
           'https://postpiloter.com/',
           'Ajans ve Marka Operasyonlarını Tek Merkezde Yönetin',
           'Brieflerden kreatif onaya, revizyondan içerik takvimine tüm ajans-marka iş akışını PostPiloter ile hızlandırın.',
           'https://postpiloter.com/images/postpiloter-contact-hero.png',
           'Ajans ve Marka Brief Yönetimi | PostPiloter',
           'Brief, revizyon, onay ve içerik operasyonlarını tek merkezde yönetin.',
           true, true, now(), now()),
          (gen_random_uuid(), 'pricing',
           'Ajans Brief Yönetimi Fiyatları | PostPiloter',
           'Ajansınızın büyüklüğüne uygun PostPiloter planlarını karşılaştırın. Brief, kreatif onay, içerik takvimi ve marka portalı özelliklerini inceleyin.',
           'brief yönetim fiyatları, ajans yazılımı fiyatları, içerik onay sistemi fiyatları, marka portalı',
           'https://postpiloter.com/pricing',
           'PostPiloter Planları ve Fiyatlandırma',
           'Ajansınız için doğru brief ve kreatif operasyon planını karşılaştırın.',
           'https://postpiloter.com/images/postpiloter-contact-hero.png',
           'PostPiloter Fiyatlandırma',
           'Ajans ve marka iş akışınıza uygun planı seçin.',
           true, true, now(), now()),
          (gen_random_uuid(), 'contact',
           'PostPiloter İletişim | Satış ve Destek',
           'PostPiloter satış, demo, çözüm ortaklığı ve ürün desteği için ekibimize ulaşın. Ajans ve marka operasyonunuzu birlikte değerlendirelim.',
           'PostPiloter iletişim, ajans yazılımı demo, brief yönetim satış, kreatif operasyon desteği',
           'https://postpiloter.com/contact',
           'PostPiloter Ekibiyle İletişime Geçin',
           'Ajansınızın brief, revizyon ve müşteri onay süreçlerini birlikte sadeleştirelim.',
           'https://postpiloter.com/images/postpiloter-contact-hero.png',
           'PostPiloter İletişim',
           'Satış, demo ve ürün desteği için ekibimize ulaşın.',
           true, true, now(), now())
        ON CONFLICT (page_key) DO UPDATE SET
          title = EXCLUDED.title,
          description = EXCLUDED.description,
          keywords = EXCLUDED.keywords,
          canonical_url = EXCLUDED.canonical_url,
          og_title = EXCLUDED.og_title,
          og_description = EXCLUDED.og_description,
          og_image_url = COALESCE(platform_seo_page_settings.og_image_url, EXCLUDED.og_image_url),
          twitter_title = EXCLUDED.twitter_title,
          twitter_description = EXCLUDED.twitter_description,
          indexable = true,
          follow_links = true,
          updated_at = now()
        """
    )
    op.execute(
        """
        INSERT INTO platform_growth_settings
          (id, setting_key, robots_txt, sitemap_last_generated_at, public_app_url,
           created_at, updated_at)
        VALUES
          (gen_random_uuid(), 'default',
           E'User-agent: *\nAllow: /\nDisallow: /platform/\nDisallow: /dashboard/\nDisallow: /brand/\nDisallow: /auth/\nDisallow: /approve/\nDisallow: /report/\nDisallow: /api/\n\nSitemap: https://postpiloter.com/sitemap.xml',
           now(), 'https://postpiloter.com', now(), now())
        ON CONFLICT (setting_key) DO UPDATE SET
          robots_txt = COALESCE(platform_growth_settings.robots_txt, EXCLUDED.robots_txt),
          sitemap_last_generated_at = now(),
          public_app_url = 'https://postpiloter.com',
          updated_at = now()
        """
    )


def downgrade() -> None:
    op.drop_table("contact_submissions")
    op.drop_column("platform_seo_page_settings", "keywords")
    op.drop_index("ix_demo_sandboxes_brand_user_id", table_name="demo_sandboxes")
    op.drop_constraint(
        "fk_demo_sandboxes_brand_user_id_users",
        "demo_sandboxes",
        type_="foreignkey",
    )
    op.drop_column("demo_sandboxes", "brand_user_id")
