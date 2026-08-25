from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "PostPiloter"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    REDIS_URL: str = "redis://localhost:6379/0"
    NOTIFICATION_WS_TICKET_TTL_SECONDS: int = 60
    NOTIFICATION_WS_HEARTBEAT_SECONDS: int = 25
    NOTIFICATION_WS_RECONNECT_DELAY_SECONDS: int = 2
    DEMO_SANDBOX_TURNSTILE_SITE_KEY: str = ""
    DEMO_SANDBOX_TURNSTILE_SECRET_KEY: str = ""
    DEMO_SANDBOX_CLEANUP_INTERVAL_SECONDS: int = 300

    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ALLOW_CREDENTIALS: bool = True

    EMAIL_FROM: str = "noreply@postpiloter.com"
    EMAIL_FROM_NAME: str = "PostPiloter"

    STORAGE_BACKEND: str = "local"

    AUTH_RATE_LIMIT_ATTEMPTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 900

    PLATFORM_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    PLATFORM_ADMIN_RATE_LIMIT_ATTEMPTS: int = 5
    PLATFORM_ADMIN_RATE_LIMIT_WINDOW_SECONDS: int = 600
    PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS: int = 5
    PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS: int = 600
    PLATFORM_ADMIN_IP_ALLOWLIST: str = ""
    # Number of trusted reverse-proxy hops in front of this app (Railway's
    # edge = 1). Only this many entries from the *right* end of
    # X-Forwarded-For are ever trusted — a client can prepend arbitrary
    # spoofed entries to the header without it affecting IP resolution.
    TRUSTED_PROXY_HOP_COUNT: int = 1
    PLATFORM_BOOTSTRAP_SECRET: str = ""

    FRONTEND_URL: str = "http://localhost:3000"

    APPROVAL_TOKEN_EXPIRE_HOURS: int = 72

    MEDIA_ROOT: str = "./media"
    MAX_UPLOAD_SIZE_MB: int = 10

    TOTP_ENCRYPTION_KEY: str = ""  # Fernet key; derived from SECRET_KEY when empty (dev only)

    # Secret encryption for platform provider credentials (DB-level field encryption)
    # Generate: python -c "from cryptography.fernet import Fernet;
    #   print(Fernet.generate_key().decode())"
    FLOBRIEF_SECRET_ENCRYPTION_KEY: str = ""

    # Public URL used for action links in WhatsApp messages (ngrok/Cloudflare Tunnel in dev)
    FRONTEND_PUBLIC_URL: str = "http://localhost:3000"

    # Public URL of this API as configured in the Twilio console webhook settings.
    # Required for correct X-Twilio-Signature verification in production; falls back
    # to the incoming request's reconstructed URL when unset (dev/tunnel use).
    BACKEND_PUBLIC_URL: str = ""

    # WhatsApp feature flag (provider config stored in DB; this is a global kill switch)
    WHATSAPP_NOTIFICATIONS_ENABLED: bool = False

    # Dev/staging-only allowlisted recipient for the WhatsApp test-send flow.
    # Never used in production (see app.core.config.Settings.is_production checks
    # at each call site). Must be a number that has joined the Twilio sandbox.
    WHATSAPP_TEST_RECIPIENT: str | None = None
    WHATSAPP_DEFAULT_LOCALE: str = "tr"

    # Dev-only free-text fallback for the WhatsApp test-send flow (Part 6A).
    # Effective ONLY when every gate in whatsapp_test_send_service is also
    # satisfied (APP_ENV=development, WHATSAPP_NOTIFICATIONS_ENABLED, the
    # official Twilio Sandbox sender, WHATSAPP_TEST_RECIPIENT configured) —
    # this flag alone never bypasses the approved-template requirement in
    # staging or production. See docs/DECISIONS.md.
    WHATSAPP_SANDBOX_FREEFORM_TEST_ENABLED: bool = False

    # Resend email provider (production env is authoritative; DB-first outside production)
    RESEND_API_KEY: str = ""
    RESEND_TEST_MODE: bool = False
    RESEND_TEST_RECIPIENT: str = "delivered@resend.dev"
    RESEND_TEST_FROM_EMAIL: str = "onboarding@resend.dev"
    EMAIL_REPLY_TO: str = ""

    # iyzico billing
    IYZICO_API_KEY: str = ""
    IYZICO_SECRET_KEY: str = ""
    IYZICO_MERCHANT_ID: str = ""
    IYZICO_BASE_URL: str = "https://sandbox-api.iyzipay.com"

    # SEO growth integrations — unset means "not configured", never faked in the UI
    PAGESPEED_API_KEY: str = ""
    GOOGLE_SEARCH_CONSOLE_PROPERTY_URL: str = ""
    GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL: str = ""
    GA4_PROPERTY_ID: str = ""
    GA4_SERVICE_ACCOUNT_EMAIL: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        return v

    @field_validator("STORAGE_BACKEND")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "local":
            raise ValueError(
                "Only STORAGE_BACKEND=local is implemented; S3/R2 is not production-ready"
            )
        return normalized

    @model_validator(mode="after")
    def validate_production_public_configuration(self) -> "Settings":
        if not self.is_production:
            return self

        expected_origin = "https://postpiloter.com"
        for field_name in ("FRONTEND_URL", "FRONTEND_PUBLIC_URL", "BACKEND_PUBLIC_URL"):
            value = getattr(self, field_name).rstrip("/")
            if value != expected_origin:
                raise ValueError(f"{field_name} must be {expected_origin} in production")
        if expected_origin not in self.get_cors_origins():
            raise ValueError(f"CORS_ORIGINS must include {expected_origin} in production")
        if self.RESEND_TEST_MODE:
            raise ValueError("RESEND_TEST_MODE must be false in production")
        if self.EMAIL_FROM.lower() != "noreply@postpiloter.com":
            raise ValueError("EMAIL_FROM must be noreply@postpiloter.com in production")
        if self.EMAIL_FROM_NAME != "PostPiloter":
            raise ValueError("EMAIL_FROM_NAME must be PostPiloter in production")
        return self

    def get_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()  # type: ignore[call-arg]
