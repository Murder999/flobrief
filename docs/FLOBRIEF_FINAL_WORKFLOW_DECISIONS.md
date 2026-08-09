# Flobrief — Teknik ve Ürün Kararları

> Bu dosya implementasyon kararlarını ve gerekçelerini saklar. "Neden böyle yaptık?" sorusunun cevabı burada.

---

## Email Provider Kararları

### KARAR: Resend API, doğrudan `httpx.AsyncClient` ile çağrılıyor (SDK yok)
**Tarih**: 2026-07-11
**Gerekçe**: `resend` Python SDK async destekli değil. `httpx` zaten proje bağımlılığı. Resend API basit bir POST endpoint — SDK gereksiz ağırlık.
**Uygulama**: `resend_email_provider.py` içinde `httpx.AsyncClient` ile `POST https://api.resend.com/emails`

### KARAR: Email API key için ayrı tablo değil, `PlatformProviderSetting` modeline kolon eklendi
**Tarih**: 2026-07-11
**Gerekçe**: Twilio zaten bu modeli kullanıyor. "Bir provider = bir satır" pattern'i tutarlı. Ayrı tablo gereksiz karmaşıklık.
**Uygulama**: `provider="email_resend"` satırı, 5 yeni kolon ile

### KARAR: `email_api_key_masked` varchar(30), sabit format `re_••••••••<last4>`
**Tarih**: 2026-07-11
**Gerekçe**: İlk implementasyonda `len(key) - 7` adet bullet kullanıldı → API key 36 char → masked string 36 char → varchar(30) taşması.
Sabit 8 bullet + 4 son karakter = max 18 char. varchar(30) limitine güvenle sığıyor.
**Uygulama**: `_mask_api_key()` in `notification_providers.py` ve `seed_provider_settings.py`

### KARAR: Resend → SMTP fallback zinciri (hard failure yok)
**Tarih**: 2026-07-11
**Gerekçe**: Email teslimatı kritik değil — bildirim gönderilmezse sistem çalışmaya devam etmeli. Resend başarısız olursa SMTP'ye düşer, SMTP de başarısız olursa sessizce geçer.
**Uygulama**: `invitation_service.py` ve `notification_dispatcher.py`

### KARAR: HTML email builder'lar `email_service.py`'da module-level fonksiyon
**Tarih**: 2026-07-11
**Gerekçe**: Hem SMTP hem Resend aynı HTML'i kullanacak. Kopyalamak yerine paylaşılan fonksiyonlar. Class'a dönüştürmek gerekmez — 6 basit stateless fonksiyon yeterli.

---

## Deliverable Sistemi Kararları

### KARAR: Brand portal sadece submitted/approved/revision_requested/rejected deliverable'ları görür
**Tarih**: 2026-07-11
**Gerekçe**: Draft deliverable'lar ajans iç çalışmasıdır — müşteriye gösterilmez. Agency "Submit" ettikten sonra brand portalında görünür.
**Uygulama**: `brand_portal.py` → `LIST_VISIBLE_STATUSES = {"submitted", "approved", "revision_requested", "rejected"}`

### KARAR: `Asset.visibility` alanı: internal / client_visible / brand_reference
**Tarih**: 2026-07-11
**Gerekçe**: Aynı Asset tablosu hem agency-internal dosyaları hem müşteriye gönderilen deliverable dosyalarını hem de brand'in yüklediği referans dosyalarını tutar. Visibility ile ayrım yapılıyor.
**Uygulama**: `Asset.visibility` default="internal"; deliverable upload → "client_visible"; brand reference upload → "brand_reference"

### KARAR: `AssetLink.deliverable_id` nullable FK
**Tarih**: 2026-07-11
**Gerekçe**: Brief'e eklenen genel dosyalar deliverable'a bağlı değildir (deliverable_id=None). Sadece deliverable'a özgü dosyalar bu FK ile işaretlenir.
**Uygulama**: Alembic migration `p6q7r8s9t0u1` — nullable FK with CASCADE DELETE

### KARAR: Public approval page tamamen auth gerektirmez
**Tarih**: 2026-07-11
**Gerekçe**: Brand manager, brand user hesabı olmadan da brief'i onaylayabilmeli. Link-based erişim (token) yeterli güvenlik sağlar. Token'lar expires_at ile sınırlıdır.
**Uygulama**: `/public/approvals/[token]` → `publicApprovalApi.getByToken(token)` — no JWT required

---

## Bildirim Akışı Kararları

### KARAR: NotificationDispatcher event fan-out order'ı: in-app → email → WhatsApp
**Tarih**: (Part 10 + post-launch)
**Gerekçe**: In-app en hızlı ve kesin. Email ikinci öncelik. WhatsApp en pahalı ve en yavaş. Hata olursa bağımsız olarak handle ediliyor — biri başarısız olursa diğerleri devam ediyor.

### KARAR: `notification_deliveries` tablosu her kanal için ayrı satır tutuyor
**Tarih**: (Part 10)
**Gerekçe**: Hangi bildirimin hangi kanaldan gittiğini, provider_message_id'yi ve hataları ayrı ayrı takip etmek için. Aggregate view yerine granüler log.

### KARAR: Deadline reminder scheduler background task olarak çalışıyor
**Tarih**: Post-launch
**Gerekçe**: Cron job kurulumu yerine FastAPI `startup` event'i ile başlatılan async loop. Dev ortamında dış bağımlılık yok.

---

## Status Akışı Kararları

### KARAR: Brief status akışı (YENİ): draft → submitted → accepted → in_production → ready_for_review → approved → completed/scheduled
**Tarih**: 2026-07-11
**Gerekçe**: Brand portal üzerinden gönderilen briefler için daha granüler iş akışı. Her adım bir olayı temsil eder: brand gönderir → ajans kabul eder → üretimde → markaya teslim → marka onaylar.
**Uygulama**: `_STATUS_TRANSITIONS` dict in `brief_service.py`. Eski `in_review` akışı geriye dönük uyumluluk için korundu (agency→brand direct flow).

### KARAR: Eski `in_review` akışı korundu (backward compat)
**Tarih**: 2026-07-11
**Gerekçe**: Platform üzerinde zaten `in_review` statüsünde brief'ler var. Migration yapmak yerine eski akışı (`draft → in_review → approved/revision_requested`) koruduk. Yeni brand portal akışı `submitted` ile başlar.

### KARAR: Brief status akışı (ESKİ legacy): draft → submitted → in_review → approved/revision_requested
**Tarih**: (Part 6-7)
**Gerekçe**: Standart approval workflow. `revision_requested` geri döngüsü: brief tekrar `in_review`'a geçer.

### KARAR: Agency approval ve brand approval statüsleri ayrı tutuldu
**Tarih**: Post-launch (commit `875eaa4`)
**Gerekçe**: İlk implementasyonda tek `approval_status` alanı vardı. Agency onayı ≠ Brand onayı. İkisi bağımsız değerlendirilmeli.
**Uygulama**: Brief modelinde `agency_approval_status` + `brand_approval_status` ayrımı

### KARAR: Public approval portal token-based, login gerektirmiyor
**Tarih**: (Part 7)
**Gerekçe**: Brand reviewer'ların sisteme kayıt olmadan brief onaylaması gerekiyor. Token 24 saat geçerli.

---

## Brand/Agency Yetki Kararları

### KARAR: Brand, brief request yapabiliyor (agency onayı ile aktif oluyor)
**Tarih**: Post-launch (commit `2a85f01`)
**Gerekçe**: Kullanıcı talebi. Brand'in kendi brief ihtiyaçlarını bildirmesi iş akışını hızlandırıyor. Agency onaylamadan brief aktif olmuyor.

### KARAR: `platform_admin` hiçbir tenant endpoint'ine erişemiyor
**Tarih**: (Part 4)
**Gerekçe**: Güvenlik: platform_admin JWT'sinde `agency_id` yok. `get_workspace_context()` dependency `agency_id` claim'i zorunlu kılar — platform_admin 403 alır.
**Uygulama**: `app/core/dependencies.py::get_workspace_context()`

---

## Güvenlik Kararları

### KARAR: Platform admin token ömrü 5 dakika (tenant token'dan çok daha kısa)
**Tarih**: (Part 3/13)
**Gerekçe**: Platform admin en kritik hesap. Kısa ömürlü token + refresh rotation = saldırı yüzeyi minimize.

### KARAR: Tüm secret'lar Fernet şifreli DB'de (plain text asla)
**Tarih**: (Part 10 Twilio, sonra email için de aynı)
**Gerekçe**: DB dump veya yedek sızarsa secret'lar kullanılamaz olmalı. `FLOBRIEF_SECRET_ENCRYPTION_KEY` env var'ı server'da saklanıyor.

### KARAR: WhatsApp provider şu an `twilio_sandbox` — production'a geçmeden önce değiştirilmeli
**Tarih**: 2026-07-11
**Gerekçe**: Twilio sandbox account değil production business account gerekiyor. Geçiş: provider_type'ı `twilio_production`'a değiştir, WhatsApp Business API'yi etkinleştir.

---

## UI/UX Kararları

### KARAR: Platform admin paneli: koyu tema (`#0A0A0F` base), indigo accent
**Tarih**: (Part 13)
**Gerekçe**: Tenant panel'den görsel olarak net ayrım. Admin panelinin farklı "hissettirmesi" gerekiyor. Referans: Linear dashboard, Vercel.

### KARAR: Platform notifications sayfası: 2 kanal seçici kart + tabbed settings
**Tarih**: 2026-07-11
**Gerekçe**: Eski implementasyon sadece WhatsApp'tı, Resend sonradan eklendi. Tab yapısı daha az scroll, daha net UX. Kanal seçici kart yaklaşımı: Stripe ve Vercel'in provider seçici pattern'ine benziyor.

### KARAR: Secret field component: masked display + "Değiştir" + "Sil" aksiyonları
**Tarih**: 2026-07-11
**Gerekçe**: Secret asla input'ta gösterilmemeli. "Kayıtlı" badge + son 4 hane yeterli doğrulama sağlar. Ayrı "Sil" aksiyonu = kasıtsız silme önleme (confirm dialog ile).

### KARAR: Brand portal vs Agency portal: ayrı layout, ayrı sidebar
**Tarih**: Post-launch
**Gerekçe**: Brand kullanıcısı daha basit bir arayüz görmeli — agency'nin iç araçlarına erişmemeli. `app/brand/layout.tsx` ayrı navigasyon.

---

## Calendar Sync Kararları

### KARAR: Calendar şu an sadece Flobrief içi (Google Calendar sync yok)
**Tarih**: (Part 9)
**Gerekçe**: v1 scope dışı. Takvim entegrasyonu OAuth akışı gerektirir. Post-launch roadmap'te.

---

## Deliverable/Asset Kararları

### KARAR: Asset thumbnail'ları authenticated fetch + blob URL ile gösteriliyor
**Tarih**: Post-launch (commit `00d6240`)
**Gerekçe**: Media endpoint'leri authenticated — `<img src>` doğrudan çalışmıyor (cookie/header göndermiyor). `fetch()` + `URL.createObjectURL()` pattern'i.

### KARAR: Lightbox inline, ayrı kütüphane yok
**Tarih**: Post-launch
**Gerekçe**: Bağımlılık eklemek yerine minimal inline implementation. Sadece fotoğraf tam ekran gösterimi gerekiyor — video/pdf lightbox v1 dışı.

---

### KARAR: Brand sidebar "İş Akışı" section header eklendi
**Tarih**: 2026-07-11
**Gerekçe**: Brief Ver, Brieflerim, Onaylar, Takvim, Dosyalar aynı iş akışı grubuna ait. Bölümlü navigasyon daha net hiyerarşi sağlıyor. Üç section: Genel, İş Akışı, Diğer.

### KARAR: Brand brief detail'de `canAct` koşulu güncellendi
**Tarih**: 2026-07-11
**Gerekçe**: Marka onay/revizyon butonları artık `in_review` (legacy) VEYA `ready_for_review` (yeni akış) durumlarında görünüyor. Eski akış için `source !== "brand_portal"` kontrolü korundu.

---

---

## Part 3 Kararları

### KARAR: PUBLIC_APPROVAL notification actor_user_id=None (public reviewer)
**Tarih**: 2026-07-11
**Gerekçe**: Public approval sayfası auth gerektirmez — actor bir Flobrief kullanıcısı değil. `actor_user_id=None` durumunda dispatcher herhangi bir recipient'i hariç tutmaz, tüm agency üyelerine gider.
**Uygulama**: `approval_service.py` → `actor_user_id=None`

### KARAR: BriefTask `visibility`: internal/client_visible (brand_visible değil)
**Tarih**: 2026-07-11
**Gerekçe**: `brand_reference` bir Asset visibility değeri; BriefTask için anlamlı değil. `internal` = sadece agency görür; `client_visible` = brand portalda da görünür.

### KARAR: Agency dashboard iki katmanlı KPI: üst 4 kart (genel), alt KPI section (operasyon)
**Tarih**: 2026-07-11
**Gerekçe**: Mevcut 4 kart (marka/üye/brief/onay) genel genel bakış için yeterli. 10 ek KPI kartı operasyon detayı için ayrı bölüm olarak eklendi. Tek bir 14-kart grid'den daha okunabilir.

### KARAR: Deliverable notification recipient = brand members (submitted) / agency members (approved/revision)
**Tarih**: 2026-07-11
**Gerekçe**: Deliverable ajans → marka yönünde → submit bildirimi markaya gider. Marka onay/revizyon kararı → ajansa gider. Mantık: "alıcı" işlemi değerlendiren taraf.

## Son Güncelleme

- Tarih: 2026-07-11
- Part 3: TAMAMLANDI — 833/833 PASS
- Güncelleyen: Claude Sonnet 4.6
