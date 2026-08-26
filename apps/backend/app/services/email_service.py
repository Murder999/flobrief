import logging
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import NotificationDeliveryStatus
from app.services.email_i18n import email_text, normalize_email_locale, render_email
from app.services.resend_email_provider import (
    EmailDeliveryResult,
    EmailProviderFactory,
)
from app.services.url_builder import url_builder

logger = logging.getLogger(__name__)


def build_agency_invite_html(
    inviter_name: str,
    agency_name: str,
    role: str,
    accept_url: str,
    message: str | None = None,
    locale: str | None = None,
) -> str:
    lang = normalize_email_locale(locale)
    extra = f'<p style="color:#8888A8;margin:12px 0">{escape(message)}</p>' if message else ""
    return render_email(
        title=email_text(lang, "invite_title"),
        recipient_name=None,
        body=email_text(lang, "invite_body", inviter=inviter_name, agency=agency_name, role=role),
        action_url=accept_url,
        action_label=email_text(lang, "accept_invite"),
        locale=lang,
        extra_html=extra,
    )


def build_brand_invite_html(
    inviter_name: str,
    agency_name: str,
    brand_name: str,
    role: str,
    accept_url: str,
    message: str | None = None,
    locale: str | None = None,
) -> str:
    lang = normalize_email_locale(locale)
    extra = f'<p style="color:#8888A8;margin:12px 0">{escape(message)}</p>' if message else ""
    return render_email(
        title=email_text(lang, "brand_invite_title"),
        recipient_name=None,
        body=email_text(
            lang,
            "brand_invite_body",
            inviter=inviter_name,
            agency=agency_name,
            brand=brand_name,
            role=role,
        ),
        action_url=accept_url,
        action_label=email_text(lang, "accept_invite"),
        locale=lang,
        extra_html=extra,
    )


def build_brief_approval_request_html(
    recipient_name: str,
    agency_name: str,
    brief_title: str,
    approval_url: str,
    locale: str | None = None,
) -> str:
    lang = normalize_email_locale(locale)
    return render_email(
        title=email_text(lang, "approval_title"),
        recipient_name=recipient_name,
        body=email_text(lang, "approval_body", agency=agency_name, brief=brief_title),
        action_url=approval_url,
        action_label=email_text(lang, "open_brief"),
        locale=lang,
    )


def build_brief_revision_requested_html(
    recipient_name: str,
    brief_title: str,
    revision_note: str,
    brief_url: str,
    locale: str | None = None,
) -> str:
    lang = normalize_email_locale(locale)
    note = f'<blockquote style="border-left:3px solid #F59E0B;margin:0 0 20px;padding:10px 14px">{escape(revision_note)}</blockquote>'
    return render_email(
        title=email_text(lang, "revision_title"),
        recipient_name=recipient_name,
        body=email_text(lang, "revision_body", brief=brief_title),
        action_url=brief_url,
        action_label=email_text(lang, "open_brief"),
        locale=lang,
        accent="#F59E0B",
        extra_html=note,
    )


def build_brief_approved_html(
    recipient_name: str, brief_title: str, brief_url: str, locale: str | None = None
) -> str:
    lang = normalize_email_locale(locale)
    return render_email(
        title=email_text(lang, "approved_title"),
        recipient_name=recipient_name,
        body=email_text(lang, "approved_body", brief=brief_title),
        action_url=brief_url,
        action_label=email_text(lang, "open_brief"),
        locale=lang,
        accent="#10B981",
    )


def build_generic_notification_html(
    recipient_name: str,
    title: str,
    body: str,
    action_url: str,
    action_label: str | None = None,
    locale: str | None = None,
) -> str:
    lang = normalize_email_locale(locale)
    return render_email(
        title=title,
        recipient_name=recipient_name,
        body=escape(body),
        action_url=action_url,
        action_label=action_label or email_text(lang, "view"),
        locale=lang,
    )


# ── HTML builder functions (module-level for reuse in Resend provider) ─────────


def _legacy_build_agency_invite_html(
    inviter_name: str,
    agency_name: str,
    role: str,
    accept_url: str,
    message: str | None = None,
) -> str:
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Davet Aldınız</h2>
    <p style="color:#8888A8;margin-bottom:8px">
      <strong style="color:#F0F0F8">{inviter_name}</strong> sizi
      <strong style="color:#F0F0F8">{agency_name}</strong> ajansına
      <strong style="color:#6366F1">{role}</strong> rolüyle davet etti.
    </p>{msg_block}
    <a href="{accept_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:24px;">Daveti Kabul Et</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu davet 7 gün geçerlidir. PostPiloter hesabınız yoksa bağlantıya tıklayarak oluşturabilirsiniz.</p>
  </div>
</body>
</html>"""


def _legacy_build_brand_invite_html(
    inviter_name: str,
    agency_name: str,
    brand_name: str,
    role: str,
    accept_url: str,
    message: str | None = None,
) -> str:
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Marka Daveti</h2>
    <p style="color:#8888A8;margin-bottom:8px">
      <strong style="color:#F0F0F8">{inviter_name}</strong> ({agency_name}) sizi
      <strong style="color:#F0F0F8">{brand_name}</strong> markasına
      <strong style="color:#6366F1">{role}</strong> rolüyle davet etti.
    </p>{msg_block}
    <a href="{accept_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:24px;">Daveti Kabul Et</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu davet 7 gün geçerlidir.</p>
  </div>
</body>
</html>"""


def _legacy_build_brief_approval_request_html(
    recipient_name: str,
    agency_name: str,
    brief_title: str,
    approval_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Onay İsteği</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px"><strong style="color:#F0F0F8">{agency_name}</strong> ajansı <strong style="color:#F0F0F8">{brief_title}</strong> başlıklı briefi onayınıza sundu.</p>
    <a href="{approval_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def _legacy_build_brief_revision_requested_html(
    recipient_name: str,
    brief_title: str,
    revision_note: str,
    brief_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Revizyon İstendi</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:16px"><strong style="color:#F0F0F8">{brief_title}</strong> briefi için revizyon talep edildi.</p>
    <p style="color:#F0F0F8;background:#1A1A24;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px;margin-bottom:24px;">{revision_note}</p>
    <a href="{brief_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def _legacy_build_brief_approved_html(
    recipient_name: str,
    brief_title: str,
    brief_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px;color:#10B981">Brief Onaylandı</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px"><strong style="color:#F0F0F8">{brief_title}</strong> başlıklı brief onaylandı.</p>
    <a href="{brief_url}" style="display:inline-block;background:#10B981;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def _legacy_build_generic_notification_html(
    recipient_name: str,
    title: str,
    body: str,
    action_url: str,
    action_label: str = "Görüntüle",
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">{title}</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">{body}</p>
    <a href="{action_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">{action_label}</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


# ── Internal helpers ────────────────────────────────────────────────────────────


def _build_verification_html(
    full_name: str, verification_url: str, locale: str | None = None
) -> str:
    lang = normalize_email_locale(locale)
    return render_email(
        title=email_text(lang, "verify_title"),
        recipient_name=None,
        body=email_text(lang, "verify_body", name=full_name),
        action_url=verification_url,
        action_label=email_text(lang, "verify_action"),
        locale=lang,
    )


def _legacy_build_verification_html(full_name: str, verification_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Inter, sans-serif; background: #0A0A0F; color: #F0F0F8; padding: 40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">E-posta adresinizi doğrulayın</h2>
    <p style="color: #8888A8; margin-bottom: 24px;">
      Merhaba {full_name}, hesabınızı aktifleştirmek için aşağıdaki bağlantıya tıklayın.
    </p>
    <a href="{verification_url}"
       style="display: inline-block; background: #6366F1; color: #fff; padding: 12px 24px;
              border-radius: 8px; text-decoration: none; font-weight: 600;">
      E-posta Adresini Doğrula
    </a>
    <p style="color: #8888A8; font-size: 12px; margin-top: 24px;">
      Bu bağlantı 24 saat geçerlidir. İstek sizden gelmediyse bu e-postayı yok sayın.
    </p>
  </div>
</body>
</html>"""


def _build_reset_html(full_name: str, reset_url: str, locale: str | None = None) -> str:
    lang = normalize_email_locale(locale)
    return render_email(
        title=email_text(lang, "reset_title"),
        recipient_name=None,
        body=email_text(lang, "reset_body", name=full_name),
        action_url=reset_url,
        action_label=email_text(lang, "reset_action"),
        locale=lang,
    )


def _legacy_build_reset_html(full_name: str, reset_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Inter, sans-serif; background: #0A0A0F; color: #F0F0F8; padding: 40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Şifre Sıfırlama</h2>
    <p style="color: #8888A8; margin-bottom: 24px;">
      Merhaba {full_name}, şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın.
    </p>
    <a href="{reset_url}"
       style="display: inline-block; background: #6366F1; color: #fff; padding: 12px 24px;
              border-radius: 8px; text-decoration: none; font-weight: 600;">
      Şifremi Sıfırla
    </a>
    <p style="color: #8888A8; font-size: 12px; margin-top: 24px;">
      Bu bağlantı 1 saat geçerlidir. İstek sizden gelmediyse bu e-postayı yok sayın.
    </p>
  </div>
</body>
</html>"""


def _safe_error_category(result: EmailDeliveryResult) -> str:
    if result.status == NotificationDeliveryStatus.NOT_CONFIGURED.value:
        return "not_configured"
    message = (result.error_message or "").lower()
    if "network" in message:
        return "network"
    for code in ("401", "403", "422", "429"):
        if code in message:
            return f"http_{code}"
    return "provider_error" if result.error_message else "none"


def log_email_delivery(result: EmailDeliveryResult, *, message_type: str) -> None:
    """Log delivery metadata without recipient, token, content, or credentials."""
    if result.status == NotificationDeliveryStatus.SENT.value:
        logger.info(
            "Email delivery completed provider=%s message_type=%s status=%s",
            result.provider,
            message_type,
            result.status,
        )
        return
    logger.warning(
        "Email delivery incomplete provider=%s message_type=%s status=%s error_category=%s",
        result.provider,
        message_type,
        result.status,
        _safe_error_category(result),
    )


async def deliver_transactional_email(
    db: AsyncSession,
    *,
    to_email: str,
    subject: str,
    html_body: str,
    message_type: str,
) -> EmailDeliveryResult:
    """Deliver through the effective DB/env provider and fail non-destructively."""
    try:
        provider = await EmailProviderFactory.get_provider(db)
    except Exception as exc:
        logger.error(
            "Email provider resolution failed provider=resend message_type=%s error_type=%s",
            message_type,
            type(exc).__name__,
        )
        return EmailDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider="resend",
            provider_message_id=None,
            error_message="Provider resolution failed",
        )

    try:
        result = await provider.send(to_email=to_email, subject=subject, html=html_body)
    except Exception as exc:
        logger.error(
            "Email provider raised unexpectedly provider=%s message_type=%s error_type=%s",
            provider.get_provider_name(),
            message_type,
            type(exc).__name__,
        )
        result = EmailDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider=provider.get_provider_name(),
            provider_message_id=None,
            error_message="Unexpected provider failure",
        )

    log_email_delivery(result, message_type=message_type)
    return result


async def send_verification_email(
    db: AsyncSession, to_email: str, full_name: str, token: str, locale: str | None = None
) -> EmailDeliveryResult:
    lang = normalize_email_locale(locale)
    url = url_builder.verification_link(token)
    html = _build_verification_html(full_name, url, lang)
    return await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {email_text(lang, 'verify_title')}",
        html_body=html,
        message_type="email_verification",
    )


async def send_password_reset_email(
    db: AsyncSession, to_email: str, full_name: str, token: str, locale: str | None = None
) -> EmailDeliveryResult:
    lang = normalize_email_locale(locale)
    url = url_builder.password_reset_link(token)
    html = _build_reset_html(full_name, url, lang)
    return await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {email_text(lang, 'reset_title')}",
        html_body=html,
        message_type="password_reset",
    )


async def send_agency_invite_email(
    db: AsyncSession,
    to_email: str,
    agency_name: str,
    inviter_name: str,
    role: str,
    token: str,
    message: str | None = None,
) -> None:
    url = url_builder.invite_link(token)
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Davet Aldınız</h2>
    <p style="color:#8888A8;margin-bottom:8px">
      <strong style="color:#F0F0F8">{inviter_name}</strong> sizi
      <strong style="color:#F0F0F8">{agency_name}</strong> ajansına
      <strong style="color:#6366F1">{role}</strong> rolüyle davet etti.
    </p>{msg_block}
    <a href="{url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;margin-top:24px;">
      Daveti Kabul Et
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu davet 7 gün geçerlidir. PostPiloter hesabınız yoksa bağlantıya tıklayarak oluşturabilirsiniz.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {agency_name} Daveti",
        html_body=html,
        message_type="agency_invitation",
    )


async def send_partnership_invite_email(
    db: AsyncSession,
    *,
    to_email: str,
    source_name: str,
    inviter_name: str,
    direction: str,
    token: str,
    message: str | None = None,
    locale: str | None = None,
) -> EmailDeliveryResult:
    lang = normalize_email_locale(locale)
    if direction == "agency_invites_brand":
        title = "Marka iş ortaklığı daveti" if lang == "tr" else "Brand partnership invitation"
        body = (
            f"{escape(inviter_name)} sizi {escape(source_name)} ajansıyla marka iş ortaklığı kurmaya davet etti."
            if lang == "tr"
            else f"{escape(inviter_name)} invited your brand to partner with {escape(source_name)}."
        )
    else:
        title = "Ajans iş ortaklığı daveti" if lang == "tr" else "Agency partnership invitation"
        body = (
            f"{escape(inviter_name)} sizi {escape(source_name)} markasının ajans iş ortağı olmaya davet etti."
            if lang == "tr"
            else f"{escape(inviter_name)} invited your agency to partner with {escape(source_name)}."
        )
    extra = f'<p style="color:#8888A8;margin:12px 0">{escape(message)}</p>' if message else ""
    html = render_email(
        title=title,
        recipient_name=None,
        body=body,
        action_url=url_builder.partnership_invite_link(token),
        action_label="Daveti incele" if lang == "tr" else "Review invitation",
        locale=lang,
        extra_html=extra,
    )
    return await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {title}",
        html_body=html,
        message_type="partnership_invitation",
    )


async def send_brief_approval_request_email(
    db: AsyncSession,
    to_email: str,
    recipient_name: str,
    agency_name: str,
    brief_title: str,
    approval_url: str,
) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Onay İsteği</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">
      <strong style="color:#F0F0F8">{agency_name}</strong> ajansı
      <strong style="color:#F0F0F8">{brief_title}</strong> başlıklı briefi onayınıza sundu.
    </p>
    <a href="{approval_url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Briefe Git
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — Onay Bekleniyor: {brief_title}",
        html_body=html,
        message_type="brief_approval_request",
    )


async def send_brief_revision_requested_email(
    db: AsyncSession,
    to_email: str,
    recipient_name: str,
    brief_title: str,
    revision_note: str,
    brief_url: str,
) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Revizyon İstendi</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:16px">
      <strong style="color:#F0F0F8">{brief_title}</strong> briefi için revizyon talep edildi.
    </p>
    <p style="color:#F0F0F8;background:#1A1A24;border-left:3px solid #F59E0B;
              padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px;margin-bottom:24px;">
      {revision_note}
    </p>
    <a href="{brief_url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Briefe Git
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — Revizyon İstendi: {brief_title}",
        html_body=html,
        message_type="brief_revision_requested",
    )


async def send_brief_approved_email(
    db: AsyncSession,
    to_email: str,
    recipient_name: str,
    brief_title: str,
    brief_url: str,
) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px;color:#10B981">Brief Onaylandı</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">
      <strong style="color:#F0F0F8">{brief_title}</strong> başlıklı brief onaylandı.
    </p>
    <a href="{brief_url}"
       style="display:inline-block;background:#10B981;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Briefe Git
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — Onaylandı: {brief_title}",
        html_body=html,
        message_type="brief_approved",
    )


async def send_generic_notification_email(
    db: AsyncSession,
    to_email: str,
    recipient_name: str,
    title: str,
    body: str,
    action_url: str,
) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">{title}</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">{body}</p>
    <a href="{action_url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Görüntüle
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {title}",
        html_body=html,
        message_type="generic_notification",
    )


async def send_payment_failed_email(
    db: AsyncSession,
    to_email: str,
    recipient_name: str,
    agency_name: str,
    billing_url: str,
) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px;color:#EF4444">Ödeme Başarısız</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">
      <strong style="color:#F0F0F8">{agency_name}</strong> hesabınızın ödemesi alınamadı.
      Hizmet kesintisini önlemek için ödeme bilgilerinizi güncelleyin.
    </p>
    <a href="{billing_url}"
       style="display:inline-block;background:#EF4444;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Ödeme Bilgilerini Güncelle
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — Ödeme Başarısız",
        html_body=html,
        message_type="payment_failed",
    )


async def send_brand_invite_email(
    db: AsyncSession,
    to_email: str,
    agency_name: str,
    brand_name: str,
    inviter_name: str,
    role: str,
    token: str,
    message: str | None = None,
) -> None:
    url = url_builder.invite_link(token)
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Marka Daveti</h2>
    <p style="color:#8888A8;margin-bottom:8px">
      <strong style="color:#F0F0F8">{inviter_name}</strong> ({agency_name}) sizi
      <strong style="color:#F0F0F8">{brand_name}</strong> markasına
      <strong style="color:#6366F1">{role}</strong> rolüyle davet etti.
    </p>{msg_block}
    <a href="{url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;margin-top:24px;">
      Daveti Kabul Et
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu davet 7 gün geçerlidir.
    </p>
  </div>
</body>
</html>"""
    await deliver_transactional_email(
        db,
        to_email=to_email,
        subject=f"{settings.EMAIL_FROM_NAME} — {brand_name} Marka Daveti",
        html_body=html,
        message_type="brand_invitation",
    )
