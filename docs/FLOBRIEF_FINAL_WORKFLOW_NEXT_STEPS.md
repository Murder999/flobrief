# Flobrief — Next Steps (Context Resume Kılavuzu)

> Bu dosya context kesildiğinde veya oturum sona erdiğinde kaldığın yerden devam etmek için kullanılır.
> Yeni oturuma başlarken önce bu dosyayı oku, sonra STATE ve PROGRESS dosyalarını kontrol et.

---

## ŞUANKI KONUM (2026-07-11)

### Tamamlanan Son İş (Part 3 — Bildirimler, KPI, BriefTask)

**Backend:**
- 6 yeni `NotificationEventType` (toplam 24)
- `BriefTask` model + Alembic migration `q7r8s9t0u1v2`
- BriefTask CRUD router (4 endpoint)
- Agency KPI dashboard: `GET /api/v1/dashboard/agency-kpis`
- Agency workload: `GET /api/v1/dashboard/workload`
- Brand KPI: `GET /api/v1/brand-portal/dashboard/kpis`
- Notification wiring: deliverable.submitted/approved/revision_requested
- Notification wiring: milestone.assigned
- Notification wiring: public_approval.approved/revision_requested
- NotificationDispatcher 24 event destekliyor
- 26 yeni test → 833/833 PASS, ruff PASS

**Frontend:**
- Agency dashboard: 10 KPI kartı (real DB data)
- Brand dashboard: 8 KPI kartı (real DB data)
- `AgencyKPIStats`, `BrandKPIStats`, `dashboardApi` → api-client.ts
- tsc PASS, build PASS

### Bir Sonraki Oturumda İlk Yapılacak

1. **Git log kontrol et**: `git log --oneline -5`
2. **Test çalıştır**: `cd apps/backend && python -m pytest app/tests/ -q --tb=no`
3. **Migration uygula** (Docker DB çalışıyorsa): `alembic upgrade head`

---

## ÖNCELİKLİ GÖREVLER (sıralı)

### GÖREV 1 — Alembic Migration Uygula
```
cd apps/backend
alembic upgrade head
```
`brief_tasks` ve `deliverables` tabloları oluşacak.

### GÖREV 2 — BriefTask Frontend UI
API hazır (`/briefs/{id}/tasks`), frontend eksik.
Agency brief detail sayfasına "Görevler" tab'ı ekle:
- `GET /briefs/{brief_id}/tasks` → liste
- `POST /briefs/{brief_id}/tasks` → yeni görev
- `PATCH /briefs/{brief_id}/tasks/{task_id}` → status/assignee güncelle
- Sadece `visibility=client_visible` olanlar brand portalda görünür

### GÖREV 3 — Manuel QA: Deliverable + Notification Akışı
1. Deliverable submit → brand portalda görünür mü?
2. Brand onaylar → agency notification delivery oluşuyor mu?
3. Public approval approve → agency notification gidiyor mu?
4. Milestone ata → atanan kişi notification alıyor mu?

### GÖREV 4 — Platform SEO Settings Tamamlanması
**Dosyalar**:
- Backend: `apps/backend/app/api/v1/platform/seo.py`
- Frontend: `apps/frontend/app/platform/seo/page.tsx`

### GÖREV 5 — Üretim Deployment
Kullanıcı deploy etmeye karar verirse:
1. `.env.prod` oluşturulacak
2. `make docker-build` → `make docker-up`
3. Alembic upgrade head
4. Seed plans + platform admin

---

## CONTEXT KESİLİRSE — DEVAM PROMPTU

```
Flobrief projesine devam ediyorum. Proje C:\Users\buse3\Desktop\Flobrief dizininde.

Lütfen şu dosyaları oku ve durumu kavra:
1. docs/FLOBRIEF_FINAL_WORKFLOW_STATE.md
2. docs/FLOBRIEF_FINAL_WORKFLOW_PROGRESS.md
3. docs/FLOBRIEF_FINAL_WORKFLOW_NEXT_STEPS.md

Son commit: git log --oneline -5 ile kontrol et.
Test durumu: cd apps/backend && python -m pytest app/tests/ -q --tb=no

Part 1, Part 2, Part 3 tamamlandı. Son commit Part 3.
Durumu kavradıktan sonra NEXT_STEPS dosyasındaki bir sonraki göreve geç.
Yeni bir şey başlatma, sadece kaldığın yerden devam et.
```

---

## ÖNEMLİ TEKNİK NOTLAR

### Notification Mimarisi
- `NotificationDispatcher.emit()` → in-app + email + whatsapp fan-out
- Actor kendi aksiyonundan bildirim almaz (`actor_user_id` hariç tutulur)
- Provider yoksa `skipped/not_configured` — ana işlemi bozmaz
- 24 event type → hepsi `_EVENT_TITLES`, email subject, HTML, WhatsApp body'de tanımlı

### KPI Endpoint'leri
- `GET /api/v1/dashboard/agency-kpis` → `AgencyKPIStats`
- `GET /api/v1/dashboard/workload` → `AgencyWorkloadStats`
- `GET /api/v1/brand-portal/dashboard/kpis` → `BrandKPIStats`
- Frontend: `dashboardApi.agencyKpis()`, `brandPortalApi.kpis()`

### Migration Zinciri
```
o5p6q7r8s9t0 (email provider fields)
  → p6q7r8s9t0u1 (deliverables)
    → q7r8s9t0u1v2 (brief_tasks)  ← SON
```

### Güvenlik
- `platform_admin` JWT'sinde `agency_id` yok
- API key'ler asla raw dönmez (Fernet şifrelemesi)
- Provider secretları loglanmaz

---

## Son Güncelleme

- Tarih: 2026-07-11
- Part 3 TAMAMLANDI
- Toplam test: 833/833 PASS
- Güncelleyen: Claude Sonnet 4.6
