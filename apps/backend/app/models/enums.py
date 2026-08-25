from enum import StrEnum


class UserType(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    AGENCY_USER = "agency_user"
    BRAND_USER = "brand_user"


class AgencyStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AgencyMemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    BRAND_MANAGER = "brand_manager"
    DESIGNER = "designer"
    DEVELOPER = "developer"
    SOCIAL_MEDIA_MANAGER = "social_media_manager"
    VIEWER = "viewer"


class AgencyMemberStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class BrandStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DELETED = "deleted"


class BrandMemberRole(StrEnum):
    BRAND_OWNER = "brand_owner"
    BRAND_MANAGER = "brand_manager"
    BRAND_VIEWER = "brand_viewer"
    EXTERNAL_APPROVER = "external_approver"


class BrandMemberStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class PlanCode(StrEnum):
    STARTER_AGENCY = "starter_agency"
    PRO_AGENCY = "pro_agency"
    AGENCY_PLUS = "agency_plus"
    BRAND_SOLO = "brand_solo"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingProvider(StrEnum):
    MANUAL = "manual"
    IYZICO = "iyzico"


class BriefStatus(StrEnum):
    DRAFT = "draft"
    # Brand portal flow
    SUBMITTED = "submitted"  # Brand ajansa gönderdi
    ACCEPTED = "accepted"  # Ajans talebi kabul etti
    IN_PRODUCTION = "in_production"  # Ajans üretime başladı
    READY_FOR_REVIEW = "ready_for_review"  # Ajans markaya teslim etti
    REVISION_REQUESTED = "revision_requested"  # Marka revizyon istedi
    APPROVED = "approved"  # Marka onayladı
    REJECTED = "rejected"  # Marka reddetti
    COMPLETED = "completed"  # İş tamamlandı
    SCHEDULED = "scheduled"  # Takvime alındı
    ARCHIVED = "archived"
    # Legacy (agency→brand direct approval flow)
    IN_REVIEW = "in_review"


class BriefPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ThreadType(StrEnum):
    BRIEF = "brief"
    FIELD = "field"
    ASSET = "asset"
    APPROVAL = "approval"


class ThreadStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class CommentVisibility(StrEnum):
    INTERNAL = "internal"
    CLIENT_VISIBLE = "client_visible"


class OnboardingType(StrEnum):
    AGENCY_OWNER_ADMIN = "agency_owner_admin"
    AGENCY_MEMBER = "agency_member"
    BRAND_USER = "brand_user"


class OnboardingStepStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class MentionSourceType(StrEnum):
    """Where a mention was authored. Maps 1:1 onto the three existing free-text
    comment surfaces (comment_threads/comments, deliverable_annotations,
    annotation_replies) — mentions never introduce a fourth comment table."""

    COMMENT = "comment"
    ANNOTATION = "annotation"
    ANNOTATION_REPLY = "annotation_reply"


class StorageProvider(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    R2 = "r2"


class CalendarItemType(StrEnum):
    POST = "post"
    STORY = "story"
    REELS = "reels"
    VIDEO = "video"
    CAMPAIGN = "campaign"
    BLOG = "blog"
    EMAIL = "email"
    AD_CREATIVE = "ad_creative"
    MEETING = "meeting"
    CUSTOM = "custom"


class CalendarPlatform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    X = "x"
    YOUTUBE = "youtube"
    WEBSITE = "website"
    EMAIL = "email"
    OTHER = "other"


class CalendarItemStatus(StrEnum):
    PLANNED = "planned"
    IN_DESIGN = "in_design"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class BrandingAssetType(StrEnum):
    LOGO = "logo"
    EMAIL_LOGO = "email_logo"
    FAVICON = "favicon"
    SOCIAL_PREVIEW = "social_preview"


class CustomDomainStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    DISABLED = "disabled"


class ReportType(StrEnum):
    MONTHLY_BRAND = "monthly_brand"
    AGENCY_OVERVIEW = "agency_overview"
    CAMPAIGN_SUMMARY = "campaign_summary"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    SHARED = "shared"
    ARCHIVED = "archived"


class NotificationChannel(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    PASSIVE = "passive"
    NOT_CONFIGURED = "not_configured"
    # WhatsApp template-gated test-send flow (Part 6A) — additive, existing
    # per-event dispatcher statuses above are unchanged.
    QUEUED = "queued"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    READ = "read"
    SKIPPED_DISABLED = "skipped_disabled"
    SKIPPED_NO_CONSENT = "skipped_no_consent"
    SKIPPED_NO_PHONE = "skipped_no_phone"
    SKIPPED_UNVERIFIED_PHONE = "skipped_unverified_phone"
    SKIPPED_TEMPLATE_MISSING = "skipped_template_missing"
    SKIPPED_DEMO_TENANT = "skipped_demo_tenant"
    # Part 6B-2 — the recipient turned this specific event's WhatsApp toggle
    # off, distinct from the master SKIPPED_NO_CONSENT (which means no
    # WhatsApp consent at all).
    SKIPPED_EVENT_DISABLED = "skipped_event_disabled"
    # Part 6B-3 — terminal lifecycle states for the delivery state machine.
    # CANCELLED: a pending retry was cancelled (e.g. STOP/opt-out mid-retry).
    # EXPIRED: retry eligibility window elapsed before a send could succeed.
    # SKIPPED_ROLE: retry-time re-validation found the recipient no longer
    # role-eligible (immediate dispatch still uses the generic SKIPPED for
    # this — see whatsapp_recipient_gate — kept unchanged to avoid touching
    # already-accepted Part 6B-1/6B-2 behavior).
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SKIPPED_ROLE = "skipped_role"


class NotificationEventType(StrEnum):
    BRIEF_CREATED = "brief.created"
    BRIEF_UPDATED = "brief.updated"
    BRIEF_SUBMITTED = "brief.submitted_for_approval"
    BRIEF_REQUESTED = "brief.requested"
    BRIEF_ACCEPTED = "brief.accepted"
    BRIEF_PRODUCTION_STARTED = "brief.production_started"
    BRIEF_READY_FOR_REVIEW = "brief.ready_for_review"
    BRIEF_REVISION_REQUESTED = "brief.revision_requested"
    BRIEF_APPROVED = "brief.approved"
    BRIEF_REJECTED = "brief.rejected"
    BRIEF_COMPLETED = "brief.completed"
    BRIEF_ASSIGNED = "brief.assigned"
    BRIEF_OVERDUE = "brief.overdue"
    COMMENT_ADDED = "comment.added"
    FILE_UPLOADED = "file.uploaded"
    CALENDAR_ITEM_CREATED = "calendar.item_created"
    CALENDAR_ITEM_DUE = "calendar.item_due"
    CALENDAR_ITEM_PUBLISHED = "calendar.item_published"
    USER_INVITED = "user.invited"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription.payment_failed"
    SUBSCRIPTION_CHANGED = "subscription.changed"
    # Deliverable events
    DELIVERABLE_SUBMITTED = "deliverable.submitted"
    DELIVERABLE_APPROVED = "deliverable.approved"
    DELIVERABLE_REVISION_REQUESTED = "deliverable.revision_requested"
    # Public approval events
    PUBLIC_APPROVAL_APPROVED = "public_approval.approved"
    PUBLIC_APPROVAL_REVISION_REQUESTED = "public_approval.revision_requested"
    # Milestone events
    MILESTONE_ASSIGNED = "milestone.assigned"
    # Annotation events
    ANNOTATION_CREATED = "annotation.created"
    ANNOTATION_RESOLVED = "annotation.resolved"
    ANNOTATION_REPLIED = "annotation.replied"
    ANNOTATION_REOPENED = "annotation.reopened"
    # Mention events
    MENTIONED_IN_COMMENT = "mention.in_comment"
    MENTIONED_IN_ANNOTATION = "mention.in_annotation"
    # Time tracking events
    TIME_ENTRY_LONG_RUNNING = "time_entry.long_running"
    TIME_ENTRY_STILL_RUNNING_EOD = "time_entry.still_running_eod"
    TIMESHEET_MISSING = "timesheet.missing"
    TIME_ENTRY_APPROVAL_PENDING = "time_entry.approval_pending"
    BRIEF_ESTIMATE_OVERRUN = "brief.estimate_overrun"
    # Capacity + finance events (Part 2, Phase 7 — plan §14)
    INVOICE_SENT = "invoice.sent"
    INVOICE_APPROVAL_PENDING = "invoice.approval_pending"
    INVOICE_SEND_FAILED = "invoice.send_failed"
    INVOICE_OVERDUE = "invoice.overdue"
    INVOICE_DUE_SOON = "invoice.due_soon"
    INVOICE_PAYMENT_RECEIVED = "invoice.payment_received"
    TIME_OFF_APPROVED = "time_off.approved"
    TIME_OFF_REJECTED = "time_off.rejected"
    CAPACITY_OVER_THRESHOLD = "capacity.over_threshold"
    COMMERCIAL_TERMS_EXPIRING = "commercial_terms.expiring"
    RETAINER_OVERAGE = "retainer.overage"
    CRITICAL_WORK_UNASSIGNED = "capacity.critical_work_unassigned"


class WhatsAppProviderType(StrEnum):
    DISABLED = "disabled"
    TWILIO_SANDBOX = "twilio_sandbox"
    TWILIO_PRODUCTION = "twilio_production"
    FUTURE_PROVIDER = "future_provider"


class WhatsAppTemplateStatus(StrEnum):
    """Approval status for the WhatsApp template registry (whatsapp_templates table).

    A template not existing for an event_type/locale is "missing" — that is a
    computed condition (no row found), never a stored value here.
    """

    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class BillingEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BrandIdentityDocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    FAILED = "failed"


class BrandIdentityProfileStatus(StrEnum):
    DRAFT = "draft"
    AI_GENERATED = "ai_generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class CalendarMilestoneType(StrEnum):
    """Event-type taxonomy for brief-lifecycle milestones synthesized onto the calendar."""

    BRIEF_START = "brief_start"
    FIRST_DRAFT = "first_draft"
    BRAND_FEEDBACK = "brand_feedback"
    APPROVAL_DEADLINE = "approval_deadline"
    FINAL_DELIVERY = "final_delivery"
    PUBLISH_DATE = "publish_date"


class BrandIdentitySuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    COMMENT_REQUESTED = "comment_requested"


class NotificationCategory(StrEnum):
    BRIEF = "brief"
    COMMENT = "comment"
    APPROVAL = "approval"
    FILE = "file"
    DEADLINE = "deadline"
    TEAM = "team"
    SYSTEM = "system"


class BriefParticipantRole(StrEnum):
    BRAND_MANAGER = "brand_manager"
    TASK_OWNER = "task_owner"
    DESIGNER = "designer"
    SOCIAL_MEDIA_MANAGER = "social_media_manager"
    DEVELOPER = "developer"
    BRAND_REPRESENTATIVE = "brand_representative"
    EXTERNAL_APPROVER = "external_approver"
    VIEWER = "viewer"


class TimeEntryCategory(StrEnum):
    DESIGN = "design"
    COPYWRITING = "copywriting"
    SOCIAL_MEDIA = "social_media"
    CLIENT_MEETING = "client_meeting"
    INTERNAL_MEETING = "internal_meeting"
    REVISION = "revision"
    RESEARCH = "research"
    REPORTING = "reporting"
    PROJECT_MANAGEMENT = "project_management"
    OTHER = "other"


class PreviewFormat(StrEnum):
    """Platform-specific rendering shape for the Social Media Preview Center.

    Combined with the existing ``CalendarPlatform`` enum (not duplicated here)
    via a platform x format compatibility map, so an unsupported combination
    never reaches a fake preview.
    """

    FEED_SINGLE = "feed_single"
    FEED_CAROUSEL = "feed_carousel"
    STORY = "story"
    REEL = "reel"
    REEL_COVER = "reel_cover"
    GRID = "grid"
    DOCUMENT_CAROUSEL = "document_carousel"
    TEXT_POST = "text_post"


class CapacityExceptionType(StrEnum):
    REDUCED = "reduced"
    INCREASED = "increased"
    CLOSURE = "closure"


class TimeOffType(StrEnum):
    VACATION = "vacation"
    SICK = "sick"
    HOLIDAY = "holiday"
    UNPAID = "unpaid"
    OTHER = "other"


class TimeOffStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkAllocationSource(StrEnum):
    MANUAL = "manual"
    AUTO_TASK = "auto_task"
    AUTO_BRIEF = "auto_brief"


class CommercialTermsBillingModel(StrEnum):
    HOURLY = "hourly"
    FIXED_FEE = "fixed_fee"
    RETAINER = "retainer"
    PER_ITEM = "per_item"
    HYBRID = "hybrid"


class ClientInvoiceStatus(StrEnum):
    """Lifecycle of an agency->brand-client invoice (plan §3, distinct from
    `InvoiceStatus` which is PostPiloter's own SaaS subscription billing)."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ClientInvoiceDocumentType(StrEnum):
    """Never `e-fatura` — PostPiloter never claims to issue a legally-valid
    Turkish e-invoice; these are internal draft/proforma documents only
    (plan §1/§3/§12)."""

    DRAFT_INVOICE = "draft_invoice"
    PROFORMA = "proforma"


class ClientInvoiceLineSourceType(StrEnum):
    TIME_ENTRY = "time_entry"
    FIXED_FEE = "fixed_fee"
    RETAINER = "retainer"
    PER_ITEM = "per_item"
    DELIVERABLE = "deliverable"
    MANUAL = "manual"


class AccountingProvider(StrEnum):
    """`manual` is the only provider with a real implementation (plan §10) —
    the rest exist as enum values only, for future UI/schema readiness, and
    must never be dispatched to (raises `NotImplementedError` at the
    registry boundary)."""

    MANUAL = "manual"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    LOGO = "logo"
    PARASUT = "parasut"
    MIKRO = "mikro"


class ConnectorStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectorSyncStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    OTHER = "other"


class PaymentSource(StrEnum):
    MANUAL = "manual"
    CONNECTOR = "connector"


class FieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    RICH_TEXT = "rich_text"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    DATE = "date"
    URL = "url"
    NUMBER = "number"
    FILE = "file"
    COLOR = "color"
    MOODBOARD = "moodboard"
    REFERENCE_IMAGES = "reference_images"
    PLATFORM_SELECTOR = "platform_selector"
    CAMPAIGN_GOAL = "campaign_goal"
    TARGET_AUDIENCE = "target_audience"
