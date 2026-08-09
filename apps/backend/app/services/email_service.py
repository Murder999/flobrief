from app.core.config import settings
from app.services.resend_email_provider import ResendEmailProvider

# ── HTML builder functions (module-level for reuse in Resend provider) ─────────


def build_agency_invite_html(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Davet Aldınız</h2>
    <p style="color:#8888A8;margin-bottom:8px">
      <strong style="color:#F0F0F8">{inviter_name}</strong> sizi
      <strong style="color:#F0F0F8">{agency_name}</strong> ajansına
      <strong style="color:#6366F1">{role}</strong> rolüyle davet etti.
    </p>{msg_block}
    <a href="{accept_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:24px;">Daveti Kabul Et</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu davet 7 gün geçerlidir. Flobrief hesabınız yoksa bağlantıya tıklayarak oluşturabilirsiniz.</p>
  </div>
</body>
</html>"""


def build_brand_invite_html(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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


def build_brief_approval_request_html(
    recipient_name: str,
    agency_name: str,
    brief_title: str,
    approval_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Onay İsteği</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px"><strong style="color:#F0F0F8">{agency_name}</strong> ajansı <strong style="color:#F0F0F8">{brief_title}</strong> başlıklı briefi onayınıza sundu.</p>
    <a href="{approval_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta Flobrief tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def build_brief_revision_requested_html(
    recipient_name: str,
    brief_title: str,
    revision_note: str,
    brief_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Revizyon İstendi</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:16px"><strong style="color:#F0F0F8">{brief_title}</strong> briefi için revizyon talep edildi.</p>
    <p style="color:#F0F0F8;background:#1A1A24;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px;margin-bottom:24px;">{revision_note}</p>
    <a href="{brief_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta Flobrief tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def build_brief_approved_html(
    recipient_name: str,
    brief_title: str,
    brief_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px;color:#10B981">Brief Onaylandı</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px"><strong style="color:#F0F0F8">{brief_title}</strong> başlıklı brief onaylandı.</p>
    <a href="{brief_url}" style="display:inline-block;background:#10B981;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Briefe Git</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta Flobrief tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


def build_generic_notification_html(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px">{title}</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">{body}</p>
    <a href="{action_url}" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">{action_label}</a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta Flobrief tarafından otomatik gönderilmiştir.</p>
  </div>
</body>
</html>"""


# ── Internal helpers ────────────────────────────────────────────────────────────


def _build_verification_html(full_name: str, verification_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Inter, sans-serif; background: #0A0A0F; color: #F0F0F8; padding: 40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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


def _build_reset_html(full_name: str, reset_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family: Inter, sans-serif; background: #0A0A0F; color: #F0F0F8; padding: 40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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


async def _send_transactional(to_email: str, subject: str, html_body: str) -> None:
    provider = ResendEmailProvider(
        api_key=settings.RESEND_API_KEY,
        from_name=settings.EMAIL_FROM_NAME,
        from_email=settings.EMAIL_FROM,
        reply_to=settings.EMAIL_REPLY_TO or None,
        test_mode=settings.RESEND_TEST_MODE,
        test_recipient=settings.RESEND_TEST_RECIPIENT,
        test_from_email=settings.RESEND_TEST_FROM_EMAIL,
    )
    if provider.is_active():
        await provider.send(to_email=to_email, subject=subject, html=html_body)


async def send_verification_email(to_email: str, full_name: str, token: str) -> None:
    url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
    html = _build_verification_html(full_name, url)
    await _send_transactional(to_email, "Flobrief — E-posta Doğrulama", html)


async def send_password_reset_email(to_email: str, full_name: str, token: str) -> None:
    url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
    html = _build_reset_html(full_name, url)
    await _send_transactional(to_email, "Flobrief — Şifre Sıfırlama", html)


async def send_agency_invite_email(
    to_email: str,
    agency_name: str,
    inviter_name: str,
    role: str,
    token: str,
    message: str | None = None,
) -> None:
    url = f"{settings.FRONTEND_URL}/auth/accept-invite?token={token}"
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
      Bu davet 7 gün geçerlidir. Flobrief hesabınız yoksa bağlantıya tıklayarak oluşturabilirsiniz.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, f"Flobrief — {agency_name} Daveti", html)


async def send_brief_approval_request_email(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
      Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, f"Flobrief — Onay Bekleniyor: {brief_title}", html)


async def send_brief_revision_requested_email(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
      Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, f"Flobrief — Revizyon İstendi: {brief_title}", html)


async def send_brief_approved_email(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
      Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, f"Flobrief — Onaylandı: {brief_title}", html)


async def send_generic_notification_email(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
    <h2 style="font-size:18px;margin-bottom:16px">{title}</h2>
    <p style="color:#8888A8;margin-bottom:8px">Merhaba {recipient_name},</p>
    <p style="color:#8888A8;margin-bottom:24px">{body}</p>
    <a href="{action_url}"
       style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600;">
      Görüntüle
    </a>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">
      Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, f"Flobrief — {title}", html)


async def send_payment_failed_email(
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
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
      Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
    </p>
  </div>
</body>
</html>"""
    await _send_transactional(to_email, "Flobrief — Ödeme Başarısız", html)


async def send_brand_invite_email(
    to_email: str,
    agency_name: str,
    brand_name: str,
    inviter_name: str,
    role: str,
    token: str,
    message: str | None = None,
) -> None:
    url = f"{settings.FRONTEND_URL}/auth/accept-invite?token={token}"
    msg_block = f"<p style='color:#8888A8;margin-top:12px;'>{message}</p>" if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">Flobrief</h1>
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
    await _send_transactional(to_email, f"Flobrief — {brand_name} Marka Daveti", html)
