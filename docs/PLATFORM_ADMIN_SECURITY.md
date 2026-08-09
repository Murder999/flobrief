# Flobrief — Platform Admin Security Specification

## Kapsam
Bu döküman, `platform_admin` kullanıcı tipi için geçerli olan tüm güvenlik
kurallarını ve uygulama gereksinimlerini tanımlar. Tenant RBAC kuralları için
bkz. `docs/SECURITY_RULES.md`.

---

## 1. Kimlik ve Tenant Bağımsızlığı

- `platform_admin`, hiçbir `Agency` veya `Brand` tenant'ına bağlı değildir.
- `agency_member` veya `brand_member` tablosunda `platform_admin` kaydı **olamaz**.
  Bu kısıtlama service layer'da enforce edilir; DB-level constraint değil.
- `platform_admin` kullanıcısı tenant endpoint'lerine (`/api/v1/agencies/`,
  `/api/v1/briefs/`, vb.) kendi tenant haklarıyla erişemez — bu endpoint'ler
  `get_current_tenant_user()` dependency'si kullanır ve `platform_admin` gelirse
  `403 Forbidden` döner.

---

## 2. Hesap Oluşturma

- `platform_admin` oluşturmak için kayıt veya davet akışı **yoktur**.
- Tek yol: `scripts/create_platform_admin.py` CLI scripti.
  - Script interaktif şifre girişi ister (stdin, not env var).
  - Script çalışması için DB'ye doğrudan erişim + `PLATFORM_BOOTSTRAP_SECRET`
    env var doğrulaması gerekir.
  - Her çalışmada `platform_audit_logs`'a `platform_admin.created` kaydı düşer.
- Production'da bu script yalnızca deploy pipeline'ı içinden çalıştırılmalıdır;
  geliştirici terminalinden değil.

---

## 3. Kimlik Doğrulama (Authentication)

### JWT Token Ömrü
| Token türü | Tenant kullanıcı | platform_admin |
|------------|-----------------|----------------|
| Access token | 15 dakika | **5 dakika** |
| Refresh token | 30 gün | **8 saat** |

### JWT Claims — platform_admin
```json
{
  "sub": "<user_uuid>",
  "user_type": "platform_admin",
  "type": "access",
  "iat": <timestamp>,
  "exp": <timestamp>
}
```
`agency_id` ve `role` alanları **yoktur**.

### MFA / 2FA (Part 13)
- `platform_admin` için TOTP tabanlı MFA zorunludur.
- MFA tamamlanmadan access token verilmez.
- MFA seed (TOTP secret) DB'de encrypt edilmiş saklanır (`TOTP_ENCRYPTION_KEY` env var).
- Recovery kodları tek kullanımlık, bcrypt hash'li saklanır.

### Login Endpoint
- Platform admin login: `POST /api/v1/platform/auth/login`
  Tenant login endpoint'inden (`/api/v1/auth/login`) ayrıdır.
- Ortak auth endpoint dönüşünde `user_type` kontrol edilir; `platform_admin`
  gelirse normal `agency_id` claim olmaksızın token üretilir.
- Rate limit: **5 deneme / 10 dakika** per IP (tenant için 10/15dk).
- Başarısız login `platform_audit_logs`'a yazılır.

---

## 4. Yetkilendirme (Authorization)

### FastAPI Dependency
```python
# app/core/dependencies.py
async def get_platform_admin_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_access_token(token)
    if payload.get("user_type") != "platform_admin":
        raise ForbiddenError("Platform admin access required")
    user = await user_repo.get(payload["sub"])
    if not user or not user.is_active:
        raise UnauthorizedError()
    return user
```

### Endpoint Namespace
Tüm platform admin endpoint'leri `/api/v1/platform/` altındadır:
```
GET  /api/v1/platform/agencies          — tüm agency'leri listele
GET  /api/v1/platform/agencies/{id}     — agency detay
POST /api/v1/platform/agencies/{id}/suspend
POST /api/v1/platform/agencies/{id}/activate
DELETE /api/v1/platform/agencies/{id}

GET  /api/v1/platform/users             — tüm kullanıcıları listele
POST /api/v1/platform/users/{id}/deactivate
DELETE /api/v1/platform/users/{id}

GET  /api/v1/platform/subscriptions     — tüm abonelikleri listele
POST /api/v1/platform/subscriptions/{id}/override

GET  /api/v1/platform/plans             — plan listesi
POST /api/v1/platform/plans             — plan oluştur
PATCH /api/v1/platform/plans/{id}       — plan güncelle

GET  /api/v1/platform/audit-logs        — platform audit log okuma
GET  /api/v1/platform/analytics         — platform-wide istatistikler

POST /api/v1/platform/impersonate/{user_id}  — impersonate başlat
POST /api/v1/platform/impersonate/end        — impersonate bitir
```

---

## 5. Oran Sınırlama & IP Allowlist

- `/api/v1/platform/` endpoint'lerinde ayrı rate limiter uygulanır:
  **60 istek / dakika** per IP (tenant endpoint'lerinden bağımsız bucket).
- `PLATFORM_ADMIN_IP_ALLOWLIST` env var ayarlanmışsa (virgülle ayrılmış CIDR),
  bu listedeki IP'ler dışından gelen istekler `403 Forbidden` ile reddedilir.
  - Boş bırakılırsa allowlist devre dışı (geliştirme ortamı için).
  - Production'da ayarlanması şiddetle tavsiye edilir.
- Allowlist kontrolü middleware seviyesinde yapılır; endpoint'e ulaşmadan önce.

---

## 6. Audit Log (İmmutable)

### platform_audit_logs Tablosu
```sql
id           UUID PK DEFAULT gen_random_uuid()
actor_id     UUID NOT NULL FK users(id)   -- platform_admin kullanıcısı
action       VARCHAR(100) NOT NULL
             -- Örnekler: agency.suspended, user.deactivated, subscription.overridden,
             --           impersonation.started, impersonation.ended,
             --           platform_admin.login, platform_admin.login_failed,
             --           platform_admin.created, plan.updated
target_type  VARCHAR(50) NULL   -- agency | user | subscription | plan | system
target_id    UUID NULL
meta         JSONB NULL         -- önceki ve yeni değerler, sebep, vb.
ip_address   INET NULL
user_agent   TEXT NULL
created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

### Kurallar
- `UPDATE` ve `DELETE` bu tabloya **uygulanamaz** — DB-level constraint + service
  layer guard ile enforce edilir.
- Soft-delete yoktur; `deleted_at` kolonu bulunmaz.
- `platform_audit_logs` tablosuna yalnızca `INSERT` operasyonu geçerlidir.
- Her platform admin API eylemi, endpoint handler'da değil, service layer'da
  log yazımını kendi içinde tamamlamalıdır.

---

## 7. Impersonation (Kullanıcı Taklit)

Impersonation, platform admin'in bir tenant kullanıcısının görünümünü test
etmesi veya destek vermesi için kullanılır.

### Akış
1. `POST /api/v1/platform/impersonate/{user_id}` — platform_audit_logs'a yazar,
   impersonation access token üretir (`is_impersonation: true` claim ile).
2. İmpersonation token'ı standart tenant token'ı gibi çalışır; ancak
   `is_impersonation: true` flag'i tüm API yanıtlarında header olarak iletilir:
   `X-Impersonation-Active: true`.
3. `POST /api/v1/platform/impersonate/end` — impersonation sonlandırılır,
   `impersonation.ended` logu yazılır.

### Kısıtlamalar
- Impersonation sessiz değildir — tüm eylemler hem `activity_logs`'a
  (`actor_id`: impersonated user) hem de `platform_audit_logs`'a
  (`impersonation.action` meta field ile) yazılır.
- Impersonation süresi **maksimum 1 saat**; sonrasında token geçersiz olur.
- Bir `platform_admin` başka bir `platform_admin`'ı impersonate edemez.
- Impersonation token refresh edilemez.

---

## 8. Uygulama Takvimi

| Part | Kapsam |
|------|--------|
| Part 2 | `users.user_type` kolonu, `platform_audit_logs` tablosu, `create_platform_admin.py` CLI |
| Part 3 | Platform admin login endpoint, kısa ömürlü JWT, rate limit |
| Part 4 | `get_platform_admin_user()` dependency, `/api/v1/platform/` router namespace, tenant endpoint guard |
| Part 13 | Platform Admin UI, MFA/TOTP, impersonation, IP allowlist, platform analytics |
| Part 15 | Audit log integrity test, impersonation log doğrulama, platform admin güvenlik audit |
