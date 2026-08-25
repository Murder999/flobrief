# PostPiloter — Database Design Reference

## Engine
PostgreSQL 16 via SQLAlchemy 2.x async (asyncpg driver)

## Conventions
- All tables: snake_case names, plural
- Primary keys: UUID v4 (`id UUID DEFAULT gen_random_uuid()`)
- Timestamps: `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ`
- Soft delete: `deleted_at TIMESTAMPTZ NULL` (NULL = active)
- All queries filter `deleted_at IS NULL` except admin/audit views
- `agency_id` foreign key on every tenant-scoped table — indexed
- Enum types as PostgreSQL native enums or constrained VARCHAR

## Base Model Columns (All Tables)
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at  TIMESTAMPTZ NULL
```

## Core Tables (Part 2)

### agencies
```sql
id            UUID PK
name          VARCHAR(255) NOT NULL
slug          VARCHAR(100) UNIQUE NOT NULL
plan_id       UUID FK plans(id)
status        VARCHAR(20) NOT NULL DEFAULT 'trial'  -- trial|active|suspended|cancelled
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
deleted_at    TIMESTAMPTZ
```

### users
```sql
id              UUID PK
email           VARCHAR(255) UNIQUE NOT NULL
hashed_password VARCHAR(255) NOT NULL
full_name       VARCHAR(255) NOT NULL
avatar_url      TEXT NULL
user_type       VARCHAR(20) NOT NULL DEFAULT 'tenant_user'
                -- tenant_user | platform_admin
is_active       BOOLEAN NOT NULL DEFAULT TRUE
last_login_at   TIMESTAMPTZ NULL
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
deleted_at      TIMESTAMPTZ
```
`platform_admin` kullanıcıları hiçbir `agency_member` veya `brand_member` kaydına sahip olamaz.
Yalnızca CLI seed scripti veya güvenli bootstrap komutu ile oluşturulabilirler.

### agency_members
```sql
id          UUID PK
agency_id   UUID FK agencies(id) NOT NULL
user_id     UUID FK users(id) NOT NULL
role        VARCHAR(30) NOT NULL  -- agency_owner|agency_admin|agency_member
invited_by  UUID FK users(id) NULL
joined_at   TIMESTAMPTZ NULL
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
deleted_at  TIMESTAMPTZ
UNIQUE(agency_id, user_id)
```

### brands
```sql
id          UUID PK
agency_id   UUID FK agencies(id) NOT NULL
name        VARCHAR(255) NOT NULL
slug        VARCHAR(100) NOT NULL
logo_url    TEXT NULL
website     TEXT NULL
industry    VARCHAR(100) NULL
status      VARCHAR(20) NOT NULL DEFAULT 'active'
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
deleted_at  TIMESTAMPTZ
UNIQUE(agency_id, slug)
```

### brand_members
```sql
id          UUID PK
brand_id    UUID FK brands(id) NOT NULL
user_id     UUID FK users(id) NOT NULL
role        VARCHAR(30) NOT NULL  -- brand_admin|brand_viewer
invited_by  UUID FK users(id) NULL
joined_at   TIMESTAMPTZ NULL
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
deleted_at  TIMESTAMPTZ
UNIQUE(brand_id, user_id)
```

## Brief Tables (Parts 5-8)

### brief_templates
```sql
id            UUID PK
agency_id     UUID FK agencies(id) NOT NULL
name          VARCHAR(255) NOT NULL
industry      VARCHAR(100) NULL
description   TEXT NULL
sections      JSONB NOT NULL DEFAULT '[]'
is_published  BOOLEAN NOT NULL DEFAULT FALSE
created_by    UUID FK users(id) NOT NULL
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
deleted_at    TIMESTAMPTZ
```

### briefs
```sql
id              UUID PK
agency_id       UUID FK agencies(id) NOT NULL
brand_id        UUID FK brands(id) NOT NULL
template_id     UUID FK brief_templates(id) NULL
title           VARCHAR(500) NOT NULL
status          VARCHAR(30) NOT NULL DEFAULT 'draft'
                -- draft|submitted|in_review|approved|revision_requested|rejected
current_version INT NOT NULL DEFAULT 1
created_by      UUID FK users(id) NOT NULL
assigned_to     UUID FK users(id) NULL
due_date        DATE NULL
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
deleted_at      TIMESTAMPTZ
```

### brief_versions
```sql
id          UUID PK
brief_id    UUID FK briefs(id) NOT NULL
version     INT NOT NULL
content     JSONB NOT NULL
created_by  UUID FK users(id) NOT NULL
created_at  TIMESTAMPTZ
```

### brief_approvals
```sql
id              UUID PK
brief_id        UUID FK briefs(id) NOT NULL
version         INT NOT NULL
action          VARCHAR(30) NOT NULL  -- approved|revision_requested|rejected
note            TEXT NULL
acted_by        UUID FK users(id) NOT NULL
public_token    VARCHAR(64) NULL UNIQUE  -- for tokenized external access
created_at      TIMESTAMPTZ
```

### comments
```sql
id          UUID PK
brief_id    UUID FK briefs(id) NOT NULL
parent_id   UUID FK comments(id) NULL
author_id   UUID FK users(id) NOT NULL
body        TEXT NOT NULL
section_ref VARCHAR(100) NULL
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
deleted_at  TIMESTAMPTZ
```

## Calendar Tables (Part 9)

### content_posts
```sql
id            UUID PK
agency_id     UUID FK agencies(id) NOT NULL
brand_id      UUID FK brands(id) NOT NULL
brief_id      UUID FK briefs(id) NULL
title         VARCHAR(500) NOT NULL
body          TEXT NULL
platform      VARCHAR(50) NOT NULL  -- instagram|twitter|linkedin|facebook|tiktok|other
scheduled_at  TIMESTAMPTZ NOT NULL
published_at  TIMESTAMPTZ NULL
status        VARCHAR(30) NOT NULL DEFAULT 'draft'
              -- draft|scheduled|published|cancelled
created_by    UUID FK users(id) NOT NULL
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
deleted_at    TIMESTAMPTZ
```

## Platform Admin Tables (Part 2)

### platform_audit_logs
```sql
id           UUID PK
actor_id     UUID FK users(id) NOT NULL   -- must be user_type = 'platform_admin'
action       VARCHAR(100) NOT NULL         -- e.g. agency.suspend, user.deactivate
target_type  VARCHAR(50) NULL              -- agency|user|subscription|plan
target_id    UUID NULL
meta         JSONB NULL
ip_address   INET NULL
created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
```
`agency_id` yoktur — platform genelinde immutable audit kaydı.
`activity_logs`'tan ayrı tutulur çünkü tenant kapsamı dışındadır.

## Calendar Tables (Part 9)

### calendar_items
```sql
id             UUID PK
agency_id      UUID FK agencies(id) CASCADE NOT NULL  -- ix_cal_agency_id
brand_id       UUID FK brands(id) SET NULL
brief_id       UUID FK briefs(id) SET NULL
title          VARCHAR(500) NOT NULL
description    TEXT NULL
item_type      VARCHAR(30) NOT NULL DEFAULT 'post'    -- CalendarItemType enum
platform       VARCHAR(30) NOT NULL DEFAULT 'other'   -- CalendarPlatform enum
status         VARCHAR(30) NOT NULL DEFAULT 'planned' -- CalendarItemStatus enum -- ix_cal_status
publish_at     TIMESTAMPTZ NULL  -- ix_cal_publish_at
due_at         TIMESTAMPTZ NULL
color_label    VARCHAR(30) NULL
created_by_id  UUID FK users(id) SET NULL
updated_by_id  UUID FK users(id) SET NULL
created_at / updated_at / deleted_at
```
Indexes: ix_cal_agency_id, ix_cal_brand_id, ix_cal_publish_at, ix_cal_status

### calendar_item_assets (junction)
```sql
id                UUID PK
calendar_item_id  UUID FK calendar_items(id) CASCADE
asset_id          UUID FK assets(id) CASCADE
created_at / updated_at / deleted_at
```

### calendar_item_assignees (junction)
```sql
id                UUID PK
calendar_item_id  UUID FK calendar_items(id) CASCADE
user_id           UUID FK users(id) CASCADE
created_at / updated_at / deleted_at
```

### calendar_item_status_history (append-only audit)
```sql
id                UUID PK
calendar_item_id  UUID FK calendar_items(id) CASCADE
old_status        VARCHAR(30) NULL
new_status        VARCHAR(30) NOT NULL
changed_by_id     UUID FK users(id) SET NULL
created_at / updated_at / deleted_at
```

### asset_links FK added in Part 9
`calendar_item_id UUID FK calendar_items(id) SET NULL` — deferred from Part 8 migration, applied in b2c3d4e5f6g7.

## Notification / Activity Tables (Part 10)

### activity_logs
Immutable tenant-scoped audit trail. Extends `Base` directly (no updated_at / deleted_at).
No FK constraints on agency_id/brand_id/actor_user_id — survives entity deletions.
```sql
id             UUID PK
created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
agency_id      UUID NULL  -- no FK
brand_id       UUID NULL  -- no FK
actor_user_id  UUID NULL  -- no FK
action         VARCHAR(100) NOT NULL
entity_type    VARCHAR(50) NOT NULL
entity_id      UUID NULL
meta           JSONB NULL
ip_address     VARCHAR(45) NULL
user_agent     TEXT NULL
-- Indexes: ix_act_agency_id, ix_act_entity (entity_type + entity_id), ix_act_actor
```

### notification_events
Event queue. processed_at=NULL means pending.
```sql
id             UUID PK
event_type     VARCHAR(50) NOT NULL
agency_id      UUID FK agencies(id) SET NULL
brand_id       UUID FK brands(id) SET NULL
actor_user_id  UUID FK users(id) SET NULL
payload        JSONB NOT NULL DEFAULT '{}'
processed_at   TIMESTAMPTZ NULL
created_at / updated_at / deleted_at
-- Indexes: ix_nev_agency_id, ix_nev_processed
```

### notifications
In-app notifications per user.
```sql
id         UUID PK
user_id    UUID FK users(id) CASCADE NOT NULL
agency_id  UUID FK agencies(id) SET NULL
brand_id   UUID FK brands(id) SET NULL
event_id   UUID FK notification_events(id) SET NULL
title      VARCHAR(500) NOT NULL
body       TEXT NOT NULL
event_type VARCHAR(50) NOT NULL
is_read    BOOLEAN NOT NULL DEFAULT FALSE
read_at    TIMESTAMPTZ NULL
created_at / updated_at / deleted_at
-- Indexes: ix_notif_user_id, ix_notif_agency_id, ix_notif_is_read
```

### notification_preferences
One row per user, upserted lazily on first access.
```sql
id               UUID PK
user_id          UUID FK users(id) CASCADE UNIQUE NOT NULL
email_enabled    BOOLEAN NOT NULL DEFAULT TRUE
whatsapp_enabled BOOLEAN NOT NULL DEFAULT FALSE
in_app_enabled   BOOLEAN NOT NULL DEFAULT TRUE
created_at / updated_at / deleted_at
-- Index: ix_npref_user_id (unique)
```

### notification_deliveries
Delivery record per channel per event.
```sql
id                  UUID PK
notification_id     UUID FK notifications(id) SET NULL
event_id            UUID FK notification_events(id) CASCADE NOT NULL
channel             VARCHAR(20) NOT NULL  -- email|whatsapp|in_app
status              VARCHAR(20) NOT NULL  -- pending|sent|failed|skipped|passive
provider            VARCHAR(50) NOT NULL DEFAULT ''
provider_message_id VARCHAR(255) NULL
error_message       TEXT NULL
sent_at             TIMESTAMPTZ NULL
created_at / updated_at / deleted_at
-- Indexes: ix_ndel_event_id, ix_ndel_notification_id
```

### email_templates
```sql
id        UUID PK
code      VARCHAR(100) UNIQUE NOT NULL  -- e.g. "brief.approved"
subject   VARCHAR(500) NOT NULL
body_html TEXT NOT NULL  -- string.Template syntax ($variable)
body_text TEXT NOT NULL
is_active BOOLEAN NOT NULL DEFAULT TRUE
created_at / updated_at / deleted_at
```

### whatsapp_templates
```sql
id            UUID PK
code          VARCHAR(100) UNIQUE NOT NULL
template_name VARCHAR(200) NOT NULL
language_code VARCHAR(10) NOT NULL DEFAULT 'tr'
body          TEXT NOT NULL
is_active     BOOLEAN NOT NULL DEFAULT TRUE
created_at / updated_at / deleted_at
```

## Reporting Tables (Part 11)

### reports
```sql
id            UUID PK
agency_id     UUID FK agencies(id) CASCADE NOT NULL
brand_id      UUID FK brands(id) SET NULL NULL
created_by_id UUID FK users(id) SET NULL NULL
report_type   VARCHAR(30) NOT NULL  -- monthly_brand|agency_overview|campaign_summary
period_start  DATE NOT NULL
period_end    DATE NOT NULL
status        VARCHAR(20) NOT NULL DEFAULT 'draft'  -- draft|generated|shared|archived
title         VARCHAR(500) NOT NULL
created_at / updated_at / deleted_at
-- Indexes: ix_rep_agency_id, ix_rep_brand_id, ix_rep_status
```

### report_snapshots
Immutable computed metrics at generation time. Source data changes do not affect existing snapshots.
```sql
id        UUID PK
report_id UUID FK reports(id) CASCADE NOT NULL
metrics   JSONB NOT NULL DEFAULT '{}'
narrative JSONB NULL
created_at / updated_at / deleted_at
-- Index: ix_rsnap_report_id
```

### report_share_tokens
Secure public share links. Raw token never stored — SHA-256 hash only.
```sql
id                UUID PK
report_id         UUID FK reports(id) CASCADE NOT NULL
token_hash        VARCHAR(64) UNIQUE NOT NULL  -- SHA-256 hex of raw token
expires_at        TIMESTAMPTZ NOT NULL
revoked_at        TIMESTAMPTZ NULL
allow_pdf_download BOOLEAN NOT NULL DEFAULT TRUE
created_at / updated_at / deleted_at
-- Index: ix_rst_token_hash (unique)
```

## White-Label Branding Tables (Part 12)

### agency_branding_settings
One row per agency (upserted). Controls public portal appearance.
```sql
id                  UUID PK
agency_id           UUID FK agencies(id) CASCADE NOT NULL  UNIQUE
brand_name_override VARCHAR(255) NULL
primary_color       VARCHAR(7) NULL   -- #RRGGBB validated hex
secondary_color     VARCHAR(7) NULL
accent_color        VARCHAR(7) NULL
logo_asset_id       UUID FK assets(id) SET NULL NULL
email_logo_asset_id UUID FK assets(id) SET NULL NULL
favicon_asset_id    UUID FK assets(id) SET NULL NULL
custom_footer_text  VARCHAR(500) NULL
is_white_label_enabled BOOLEAN NOT NULL DEFAULT FALSE
created_at / updated_at / deleted_at
-- Index: ix_branding_agency_id, uq_branding_agency_id
```
`is_white_label_enabled` can only be set to true if `plan.white_label_enabled=True`. Enforced at service layer.

### branding_assets
Typed junction: tracks which assets are used for branding (prevents arbitrary asset exposure on public endpoint).
```sql
id         UUID PK
agency_id  UUID FK agencies(id) CASCADE NOT NULL
asset_id   UUID FK assets(id) CASCADE NOT NULL
asset_type VARCHAR(20) NOT NULL  -- logo|email_logo|favicon|social_preview
created_at / updated_at / deleted_at
-- Index: ix_ba_agency_id
```
Only assets with a BrandingAsset record are served via the public `/public/branding/assets/{id}` endpoint.
SVG files are rejected at upload time (XSS risk). Only PNG, JPEG, WebP, GIF allowed. Max 5 MB.

### custom_domain_settings
One row per agency (upserted). DNS verification token stored as SHA-256 hash.
```sql
id                      UUID PK
agency_id               UUID FK agencies(id) CASCADE NOT NULL  UNIQUE
domain                  VARCHAR(255) NOT NULL
status                  VARCHAR(20) NOT NULL DEFAULT 'pending'  -- pending|verified|failed|disabled
verification_token_hash VARCHAR(64) NULL   -- SHA-256(raw_token)
verified_at             TIMESTAMPTZ NULL
created_at / updated_at / deleted_at
-- Index: ix_cds_agency_id, uq_domain_agency_id
```
Raw verification token returned once at creation. SHA-256 hash stored. Actual DNS activation deferred to Part 15.

## Billing Tables (Part 13)

### plans
```sql
id                UUID PK
name              VARCHAR(100) NOT NULL
slug              VARCHAR(50) UNIQUE NOT NULL
max_brands        INT NULL  -- NULL = unlimited
max_users         INT NULL
storage_gb        INT NULL
features          JSONB NOT NULL DEFAULT '{}'
monthly_price_try NUMERIC(10,2) NOT NULL
annual_price_try  NUMERIC(10,2) NOT NULL
is_active         BOOLEAN NOT NULL DEFAULT TRUE
created_at        TIMESTAMPTZ
updated_at        TIMESTAMPTZ
```

### subscriptions
```sql
id                  UUID PK
agency_id           UUID FK agencies(id) UNIQUE NOT NULL
plan_id             UUID FK plans(id) NOT NULL
status              VARCHAR(20) NOT NULL  -- trial|active|past_due|cancelled
trial_ends_at       TIMESTAMPTZ NULL
current_period_start TIMESTAMPTZ NULL
current_period_end  TIMESTAMPTZ NULL
iyzico_sub_key      VARCHAR(255) NULL
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

## Indexing Strategy
- All `agency_id` columns: B-tree index
- All `brand_id` columns: B-tree index  
- `briefs.status`: B-tree index
- `content_posts.scheduled_at`: B-tree index
- `notifications.user_id` + `is_read`: composite index
- `activity_logs.entity_type` + `entity_id`: composite index
- `users.email`: unique index
