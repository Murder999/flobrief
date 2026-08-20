# ruff: noqa: E501

from html import escape
from typing import Literal

Locale = Literal["en", "tr"]


def normalize_email_locale(value: str | None) -> Locale:
    return "tr" if value == "tr" else "en"


EMAIL_COPY: dict[Locale, dict[str, str]] = {
    "en": {
        "hello": "Hello {name},",
        "automated": "This email was sent automatically by PostPiloter.",
        "view": "View",
        "open_brief": "Open brief",
        "accept_invite": "Accept invitation",
        "invite_title": "You’re invited",
        "brand_invite_title": "Brand invitation",
        "invite_body": "{inviter} invited you to the {agency} agency as {role}.",
        "brand_invite_body": "{inviter} ({agency}) invited you to the {brand} brand as {role}.",
        "invite_expiry": "This invitation is valid for 7 days.",
        "verify_title": "Verify your email address",
        "verify_body": "Hello {name}, use the link below to activate your account.",
        "verify_action": "Verify email address",
        "verify_expiry": "This link is valid for 24 hours. If you did not request it, you can ignore this email.",
        "reset_title": "Reset your password",
        "reset_body": "Hello {name}, use the link below to reset your password.",
        "reset_action": "Reset password",
        "reset_expiry": "This link is valid for 1 hour. If you did not request it, you can ignore this email.",
        "approval_title": "Approval requested",
        "approval_body": "{agency} submitted “{brief}” for your approval.",
        "revision_title": "Revision requested",
        "revision_body": "A revision was requested for “{brief}”.",
        "approved_title": "Brief approved",
        "approved_body": "“{brief}” was approved.",
        "payment_title": "Payment failed",
        "payment_body": "We could not process the payment for {agency}. Update your payment details to avoid an interruption.",
        "payment_action": "Update payment details",
    },
    "tr": {
        "hello": "Merhaba {name},",
        "automated": "Bu e-posta PostPiloter tarafından otomatik gönderilmiştir.",
        "view": "Görüntüle",
        "open_brief": "Briefe Git",
        "accept_invite": "Daveti Kabul Et",
        "invite_title": "Davet Aldınız",
        "brand_invite_title": "Marka Daveti",
        "invite_body": "{inviter} sizi {agency} ajansına {role} rolüyle davet etti.",
        "brand_invite_body": "{inviter} ({agency}) sizi {brand} markasına {role} rolüyle davet etti.",
        "invite_expiry": "Bu davet 7 gün geçerlidir.",
        "verify_title": "E-posta adresinizi doğrulayın",
        "verify_body": "Merhaba {name}, hesabınızı aktifleştirmek için aşağıdaki bağlantıyı kullanın.",
        "verify_action": "E-posta Adresini Doğrula",
        "verify_expiry": "Bu bağlantı 24 saat geçerlidir. İstek sizden gelmediyse bu e-postayı yok sayın.",
        "reset_title": "Şifre Sıfırlama",
        "reset_body": "Merhaba {name}, şifrenizi sıfırlamak için aşağıdaki bağlantıyı kullanın.",
        "reset_action": "Şifremi Sıfırla",
        "reset_expiry": "Bu bağlantı 1 saat geçerlidir. İstek sizden gelmediyse bu e-postayı yok sayın.",
        "approval_title": "Onay İsteği",
        "approval_body": "{agency}, “{brief}” başlıklı briefi onayınıza sundu.",
        "revision_title": "Revizyon İstendi",
        "revision_body": "“{brief}” briefi için revizyon talep edildi.",
        "approved_title": "Brief Onaylandı",
        "approved_body": "“{brief}” başlıklı brief onaylandı.",
        "payment_title": "Ödeme Başarısız",
        "payment_body": "{agency} hesabının ödemesi alınamadı. Kesintiyi önlemek için ödeme bilgilerinizi güncelleyin.",
        "payment_action": "Ödeme Bilgilerini Güncelle",
    },
}


def email_text(locale: str | None, key: str, **values: str) -> str:
    safe_values = {name: escape(str(value)) for name, value in values.items()}
    return EMAIL_COPY[normalize_email_locale(locale)][key].format(**safe_values)


def render_email(
    *,
    title: str,
    recipient_name: str | None,
    body: str,
    action_url: str,
    action_label: str,
    locale: str | None,
    accent: str = "#6366F1",
    extra_html: str = "",
) -> str:
    lang = normalize_email_locale(locale)
    greeting = (
        f'<p style="color:#8888A8;margin-bottom:8px">{email_text(lang, "hello", name=recipient_name)}</p>'
        if recipient_name
        else ""
    )
    return f"""<!DOCTYPE html><html lang="{lang}"><body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px"><div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px"><h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">PostPiloter</h1><h2 style="font-size:18px;margin-bottom:16px;color:{accent}">{escape(title)}</h2>{greeting}<p style="color:#8888A8;margin-bottom:16px">{body}</p>{extra_html}<a href="{escape(action_url, quote=True)}" style="display:inline-block;background:{accent};color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">{escape(action_label)}</a><p style="color:#8888A8;font-size:12px;margin-top:24px">{email_text(lang, "automated")}</p></div></body></html>"""
