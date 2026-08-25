"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { X, Sparkles, ChevronRight, SkipForward, RotateCcw } from "lucide-react";
import { onboardingApi, brandOnboardingApi, type OnboardingProgressRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { requestMobileDrawerOpen } from "@/lib/mobile-drawer-bridge";
import { SpotlightOverlay } from "./SpotlightOverlay";

/** Matches the `lg` breakpoint the desktop sidebar uses (`hidden lg:flex`
 * in dashboard/layout.tsx and brand/layout.tsx) — below it, a step's real
 * nav anchor only exists inside the mobile drawer, not the sidebar. */
const MOBILE_DRAWER_BREAKPOINT_PX = 1024;

type Variant = "agency" | "brand";

interface StepMeta {
  title: string;
  description: string;
  route: string | null;
  cta: string;
  /** data-onboarding-target selector value for the spotlight — the sidebar
   * nav href that gets the user to this step, which may differ from `route`
   * (e.g. "first_brief"'s route is the brief-creation form, but its natural
   * spotlight anchor is the "Brief'ler" nav link). Omitted for steps whose
   * target is contextual page content rather than a persistent nav anchor —
   * those fall back to SpotlightOverlay's text-only panel. */
  target?: string;
}

const AGENCY_OWNER_STEPS: Record<string, StepMeta> = {
  welcome: { title: "PostPiloter'a hoş geldiniz", description: "Kısa bir turla temel adımları birlikte tamamlayalım.", route: null, cta: "Başla" },
  agency_profile: { title: "Ajans profilini tamamla", description: "Ajans adınızı ve görünümünüzü düzenleyin.", route: "/dashboard/settings/agency", cta: "Ajans Ayarları", target: "/dashboard/settings/agency" },
  first_brand: { title: "İlk markanı ekle", description: "Yönettiğiniz markaları platforma ekleyin.", route: "/dashboard/brands", cta: "Marka Ekle", target: "/dashboard/brands" },
  invite_team: { title: "Ekip arkadaşını davet et", description: "Takımınızı ajansınıza davet edin.", route: "/dashboard/settings/members", cta: "Ekip Davet Et", target: "/dashboard/settings/members" },
  first_brief: { title: "İlk brief'ini oluştur", description: "Bir brief oluşturarak üretime başlayın.", route: "/dashboard/briefs/new", cta: "Brief Oluştur", target: "/dashboard/briefs" },
  first_deliverable: { title: "İlk teslimatı ekle", description: "Bir brief'e üretim çıktısı yükleyin.", route: "/dashboard/briefs", cta: "Briefleri Gör", target: "/dashboard/briefs" },
  preview_center: { title: "Preview Center'ı gör", description: "Sosyal medya önizleme merkezini keşfedin.", route: "/dashboard/briefs", cta: "Görüntüle", target: "/dashboard/briefs" },
  brand_portal_preview: { title: "Marka portalını önizle", description: "Müşterilerinizin göreceği portalı inceleyin.", route: "/dashboard/brands", cta: "Markaları Gör", target: "/dashboard/brands" },
  comment_mention_annotation: { title: "Yorum ve @mention akışını dene", description: "Bir brief'te yorum yazıp ekip arkadaşınızı etiketleyin.", route: "/dashboard/briefs", cta: "Brief'e Git", target: "/dashboard/briefs" },
  time_tracking: { title: "Zaman takibini aç", description: "Ekibinizin harcadığı süreyi kaydedin.", route: "/dashboard/time/my", cta: "Zaman Takibi", target: "/dashboard/time" },
  capacity: { title: "Çalışma kapasitesi belirle", description: "Ekibinizin haftalık kapasitesini tanımlayın.", route: "/dashboard/capacity/schedule", cta: "Kapasite Ayarla", target: "/dashboard/capacity" },
  notification_preferences: { title: "Bildirim tercihlerini düzenle", description: "Hangi bildirimleri nasıl almak istediğinizi seçin.", route: "/dashboard/settings/notifications", cta: "Bildirimler", target: "/dashboard/settings/notifications" },
  summary: { title: "Kurulum özeti", description: "Harika iş! Kurulumunuz tamamlandı.", route: null, cta: "Bitir" },
};

const AGENCY_MEMBER_STEPS: Record<string, StepMeta> = {
  role_intro: { title: "Rolünü ve çalışma alanını tanı", description: "Panelinize göz atın.", route: "/dashboard", cta: "Panele Git", target: "/dashboard" },
  assigned_briefs: { title: "Atandığın briefleri gör", description: "Size atanan brief'leri görüntüleyin.", route: "/dashboard/briefs", cta: "Briefler", target: "/dashboard/briefs" },
  comment_mention: { title: "Yorum ve @mention kullan", description: "Bir brief'te yorum yazıp birini etiketleyin.", route: "/dashboard/briefs", cta: "Brief'e Git", target: "/dashboard/briefs" },
  deliverable_area: { title: "Teslimat alanını gör", description: "Üretim çıktılarının yüklendiği alanı inceleyin.", route: "/dashboard/briefs", cta: "Görüntüle", target: "/dashboard/briefs" },
  timer_start: { title: "Zamanlayıcı başlat", description: "Bir görev için süre takibi başlatın.", route: "/dashboard/time/my", cta: "Zaman Takibi", target: "/dashboard/time" },
  timesheet: { title: "Timesheet'i gör", description: "Kayıtlı çalışma sürelerinizi görüntüleyin.", route: "/dashboard/time/my", cta: "Timesheet", target: "/dashboard/time" },
  notifications: { title: "Bildirimleri yönet", description: "Bildirim tercihlerinizi düzenleyin.", route: "/dashboard/settings/notifications", cta: "Bildirimler", target: "/dashboard/settings/notifications" },
};

const BRAND_USER_STEPS: Record<string, StepMeta> = {
  portal_intro: { title: "Marka portalını tanı", description: "Portalın genel görünümüne göz atın.", route: "/brand/dashboard", cta: "Panele Git", target: "/brand/dashboard" },
  view_briefs: { title: "Briefleri görüntüle", description: "Ajansınızın hazırladığı brief'leri inceleyin.", route: "/brand/briefs", cta: "Briefler", target: "/brand/briefs" },
  deliverable_preview: { title: "Teslimat önizlemesini aç", description: "Üretilen içerikleri önizleyin.", route: "/brand/briefs", cta: "Görüntüle", target: "/brand/briefs" },
  annotation: { title: "Görsel not ekle", description: "Bir teslimat üzerinde nokta bazlı not bırakın.", route: "/brand/briefs", cta: "Brief'e Git", target: "/brand/briefs" },
  comment_mention: { title: "Yorum ve @mention kullan", description: "Bir yorumda ajans ekibinden birini etiketleyin.", route: "/brand/briefs", cta: "Brief'e Git", target: "/brand/briefs" },
  request_revision: { title: "Revizyon iste", description: "Beğenmediğiniz bir teslimat için revizyon isteyin.", route: "/brand/briefs", cta: "Brief'e Git", target: "/brand/briefs" },
  approve: { title: "Onay ver", description: "Beğendiğiniz bir teslimatı onaylayın.", route: "/brand/briefs", cta: "Brief'e Git", target: "/brand/briefs" },
  calendar_invoices: { title: "Takvim ve faturaları gör", description: "İçerik takviminizi ve faturalarınızı inceleyin.", route: "/brand/calendar", cta: "Takvimi Gör", target: "/brand/calendar" },
};

function stepMetaFor(type: string, key: string): StepMeta {
  const table =
    type === "agency_owner_admin" ? AGENCY_OWNER_STEPS
    : type === "agency_member" ? AGENCY_MEMBER_STEPS
    : BRAND_USER_STEPS;
  return table[key] ?? { title: key, description: "", route: null, cta: "Git" };
}

const SESSION_KEY = "flobrief_onboarding_wizard_closed_session";

/** Agency pages are wrapped in WorkspaceProvider; brand pages are not — this
 * thin wrapper is the only place `useWorkspace()` is called, keeping the
 * shared implementation below free of conditional hook calls. */
export function AgencyOnboardingWizard() {
  const { activeAgency } = useWorkspace();
  return <OnboardingWizardImpl variant="agency" agencyId={activeAgency?.id ?? null} />;
}

export function BrandOnboardingWizard() {
  return <OnboardingWizardImpl variant="brand" agencyId={null} />;
}

interface OnboardingWizardImplProps {
  variant: Variant;
  agencyId: string | null;
}

function OnboardingWizardImpl({ variant, agencyId }: OnboardingWizardImplProps) {
  const { accessToken } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [progress, setProgress] = useState<OnboardingProgressRead | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [spotlightStepKey, setSpotlightStepKey] = useState<string | null>(null);
  const shownWelcomeRef = useRef(false);
  /** Snapshot of the walkthrough's step-key order, captured once per spotlight
   * session (see `beginSpotlight`) instead of re-derived from `incompleteSteps`
   * on every render. Without this, a "view" step (welcome, preview_center, …)
   * disappears from `incompleteSteps` the instant `handleDoNow`'s `markSeen()`
   * call completes it — before the spotlight for that very step ever renders —
   * so its own overlay would never show. */
  const spotlightOrderRef = useRef<string[] | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    if (variant === "agency" && !agencyId) return;
    try {
      const data =
        variant === "agency"
          ? await onboardingApi.getProgress(agencyId as string, accessToken)
          : await brandOnboardingApi.getProgress(accessToken);
      setProgress(data);
      if (
        !shownWelcomeRef.current &&
        !data.dismissed_at &&
        !data.current_step &&
        typeof window !== "undefined" &&
        sessionStorage.getItem(SESSION_KEY) !== "true"
      ) {
        shownWelcomeRef.current = true;
        setWelcomeOpen(true);
      }
    } catch {
      /* silent — onboarding is a non-critical enhancement layer */
    }
  }, [accessToken, agencyId, variant]);

  useEffect(() => {
    load();
  }, [load]);

  const markSeen = useCallback(
    async (stepKey: string) => {
      if (!accessToken) return;
      const data =
        variant === "agency" && agencyId
          ? await onboardingApi.markStepSeen(stepKey, agencyId, accessToken)
          : variant === "brand"
          ? await brandOnboardingApi.markStepSeen(stepKey, accessToken)
          : null;
      if (data) setProgress(data);
    },
    [accessToken, agencyId, variant]
  );

  const skipStep = useCallback(
    async (stepKey: string) => {
      if (!accessToken) return;
      const data =
        variant === "agency" && agencyId
          ? await onboardingApi.skipStep(stepKey, agencyId, accessToken)
          : variant === "brand"
          ? await brandOnboardingApi.skipStep(stepKey, accessToken)
          : null;
      if (data) setProgress(data);
    },
    [accessToken, agencyId, variant]
  );

  const dismiss = useCallback(async () => {
    if (!accessToken) return;
    const data =
      variant === "agency" && agencyId
        ? await onboardingApi.dismiss(agencyId, accessToken)
        : variant === "brand"
        ? await brandOnboardingApi.dismiss(accessToken)
        : null;
    if (data) setProgress(data);
    setPanelOpen(false);
    setWelcomeOpen(false);
  }, [accessToken, agencyId, variant]);

  const resume = useCallback(async () => {
    if (!accessToken) return;
    const data =
      variant === "agency" && agencyId
        ? await onboardingApi.resume(agencyId, accessToken)
        : variant === "brand"
        ? await brandOnboardingApi.resume(accessToken)
        : null;
    if (data) setProgress(data);
    setPanelOpen(true);
  }, [accessToken, agencyId, variant]);

  const incompleteSteps = useMemo(
    () => progress?.steps.filter((s) => !s.completed && !s.skipped) ?? [],
    [progress]
  );

  /** Starts (or continues) a spotlight walkthrough session. Captures the
   * current incomplete-step order into `spotlightOrderRef` the first time a
   * session begins — including a step that's about to be marked seen by the
   * caller — and reuses that fixed order for every subsequent step within
   * the same session, so mid-session completions never remove a step whose
   * overlay hasn't rendered yet, or renumber "ADIM X/Y" mid-walkthrough. */
  const beginSpotlight = useCallback(
    (stepKey: string) => {
      if (!spotlightOrderRef.current || !spotlightOrderRef.current.includes(stepKey)) {
        const order = incompleteSteps.map((s) => s.key);
        spotlightOrderRef.current = order.includes(stepKey) ? order : [stepKey, ...order];
      }
      setSpotlightStepKey(stepKey);
    },
    [incompleteSteps]
  );

  const endSpotlight = useCallback(() => {
    setSpotlightStepKey(null);
    spotlightOrderRef.current = null;
  }, []);

  const handleDoNow = useCallback(
    async (stepKey: string, meta: StepMeta) => {
      // Only "view" steps get marked seen here — action steps' completion is
      // recomputed live server-side from the real action, so marking them
      // seen on a mere click would be a no-op at best and misleading UX.
      const step = progress?.steps.find((s) => s.key === stepKey);
      if (step?.kind === "view") await markSeen(stepKey);
      setPanelOpen(false);
      setWelcomeOpen(false);
      if (meta.route && meta.route !== pathname) router.push(meta.route);
      beginSpotlight(stepKey);
    },
    [markSeen, router, pathname, progress, beginSpotlight]
  );

  const percent = progress?.percent_complete ?? 0;
  const isDismissed = Boolean(progress?.dismissed_at);
  const nextStep = useMemo(
    () => progress?.steps.find((s) => !s.completed && !s.skipped) ?? null,
    [progress]
  );

  const spotlightOrder = spotlightOrderRef.current ?? [];
  const spotlightIndex = spotlightOrder.findIndex((k) => k === spotlightStepKey);
  // Looked up against ALL steps (not just incompleteSteps) so a step that
  // `markSeen()` just completed still resolves and renders its own overlay.
  const spotlightStep = useMemo(
    () => progress?.steps.find((s) => s.key === spotlightStepKey) ?? null,
    [progress, spotlightStepKey]
  );
  const spotlightMeta = spotlightStep ? stepMetaFor(progress?.onboarding_type ?? "", spotlightStep.key) : null;
  const spotlightTarget = spotlightMeta?.target ?? null;

  // A nav-anchored step's real target only exists in the DOM inside the
  // mobile drawer while it's open (the desktop sidebar with the same
  // selector is CSS-hidden below `lg`, not absent — SpotlightOverlay skips
  // it via offsetParent). Force the drawer open for the duration of such a
  // step, on mobile viewports only, and close it again the moment the step
  // changes or the spotlight ends (effect cleanup covers both).
  useEffect(() => {
    if (typeof window === "undefined" || !spotlightTarget) return undefined;
    if (window.innerWidth >= MOBILE_DRAWER_BREAKPOINT_PX) return undefined;
    requestMobileDrawerOpen(true);
    return () => requestMobileDrawerOpen(false);
  }, [spotlightTarget]);

  const advanceSpotlight = (delta: number) => {
    if (spotlightIndex < 0 || spotlightOrder.length === 0) {
      endSpotlight();
      return;
    }
    const nextIndex = spotlightIndex + delta;
    if (nextIndex < 0 || nextIndex >= spotlightOrder.length) {
      endSpotlight();
      return;
    }
    const nextKey = spotlightOrder[nextIndex];
    const meta = stepMetaFor(progress?.onboarding_type ?? "", nextKey);
    void handleDoNow(nextKey, meta);
  };

  if (!progress) return null;

  return (
    <>
      {/* Floating launcher — always available, doubles as "help menu" reopen (§J) */}
      <button
        data-onboarding-launcher
        type="button"
        onClick={() => {
          if (isDismissed) { resume(); } else { setPanelOpen(true); }
        }}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 pl-2.5 pr-3.5 py-2.5 rounded-full bg-surface border border-border shadow-lg hover:shadow-xl hover:border-accent/40 transition-all group"
        aria-label="Kurulum rehberini aç"
      >
        <span className="relative w-7 h-7 flex-shrink-0">
          <svg viewBox="0 0 28 28" className="w-7 h-7 -rotate-90">
            <circle cx="14" cy="14" r="12" fill="none" stroke="var(--color-border)" strokeWidth="3" />
            <circle
              cx="14" cy="14" r="12" fill="none" stroke="url(#ob-grad)" strokeWidth="3"
              strokeDasharray={`${(percent / 100) * 75.4} 75.4`} strokeLinecap="round"
            />
            <defs>
              <linearGradient id="ob-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#7c3aed" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>
            </defs>
          </svg>
          <Sparkles className="w-3 h-3 text-accent absolute inset-0 m-auto" />
        </span>
        <span className="text-xs font-semibold text-text hidden group-hover:inline">
          {isDismissed ? "Kaldığım yerden devam et" : `Kurulum · %${percent}`}
        </span>
      </button>

      {/* Welcome modal — premium hero, shown once per fresh onboarding */}
      {welcomeOpen && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-surface border border-border shadow-2xl overflow-hidden">
            <div className="h-28 bg-gradient-to-br from-violet-600 via-fuchsia-500 to-blue-500 flex items-center justify-center relative">
              <Sparkles className="w-10 h-10 text-white/90" />
              <button
                type="button"
                onClick={() => {
                  setWelcomeOpen(false);
                  if (typeof window !== "undefined") sessionStorage.setItem(SESSION_KEY, "true");
                }}
                className="absolute top-3 right-3 w-7 h-7 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center transition-colors"
                aria-label="Kapat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6">
              <h2 className="text-lg font-semibold text-text mb-1.5">
                {variant === "brand" ? "Marka portalına hoş geldiniz" : "PostPiloter'a hoş geldiniz"}
              </h2>
              <p className="text-sm text-text-muted leading-relaxed mb-5">
                Sizi birkaç dakikada kurulumdan geçirecek kısa bir tur hazırladık — istediğiniz an
                atlayabilir, daha sonra kaldığınız yerden devam edebilirsiniz.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setWelcomeOpen(false); setPanelOpen(true); }}
                  className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-accent hover:bg-accent-hover rounded-xl transition-colors"
                >
                  Turu Başlat
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setWelcomeOpen(false);
                    if (typeof window !== "undefined") sessionStorage.setItem(SESSION_KEY, "true");
                  }}
                  className="px-4 py-2.5 text-sm font-medium text-text-muted hover:text-text border border-border rounded-xl transition-colors"
                >
                  Daha Sonra
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Slide-in panel */}
      {panelOpen && (
        <div className="fixed inset-0 z-[105]">
          <div className="absolute inset-0 bg-black/20" onClick={() => setPanelOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-full max-w-sm bg-surface border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-text">Kurulum Rehberi</h3>
                <p className="text-xs text-text-muted mt-0.5">%{percent} tamamlandı</p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={dismiss}
                  title="Turu Kapat"
                  className="text-xs text-text-muted hover:text-text px-2 py-1 rounded-lg hover:bg-surface-2 transition-colors"
                >
                  Turu Kapat
                </button>
                <button
                  type="button"
                  onClick={() => setPanelOpen(false)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
                  aria-label="Paneli kapat"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="h-1 bg-surface-2 flex-shrink-0">
              <div
                className="h-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>

            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
              {progress.steps.map((step) => {
                const meta = stepMetaFor(progress.onboarding_type, step.key);
                const isNext = nextStep?.key === step.key;
                return (
                  <div
                    key={step.key}
                    className={`rounded-xl px-3 py-2.5 border transition-colors ${
                      step.completed
                        ? "border-transparent"
                        : isNext
                        ? "border-accent/30 bg-accent/5"
                        : "border-transparent hover:bg-surface-2"
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div
                        className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border-2 ${
                          step.completed
                            ? "bg-emerald-500 border-emerald-500"
                            : step.skipped
                            ? "bg-surface-2 border-border"
                            : "border-border"
                        }`}
                      >
                        {step.completed && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        {step.skipped && !step.completed && (
                          <SkipForward className="w-2.5 h-2.5 text-text-muted" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-xs font-medium ${
                            step.completed || step.skipped ? "text-text-muted line-through" : "text-text"
                          }`}
                        >
                          {meta.title}
                        </p>
                        {!step.completed && !step.skipped && (
                          <>
                            <p className="text-[11px] text-text-muted mt-0.5 leading-snug">{meta.description}</p>
                            <div className="flex items-center gap-2 mt-1.5">
                              <button
                                type="button"
                                onClick={() => handleDoNow(step.key, meta)}
                                className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent hover:text-accent-hover"
                              >
                                {meta.cta}
                                <ChevronRight className="w-3 h-3" />
                              </button>
                              <button
                                type="button"
                                onClick={() => skipStep(step.key)}
                                className="text-[11px] text-text-muted hover:text-text"
                              >
                                Bu Adımı Geç
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Resume affordance for a dismissed tour, surfaced inline near the launcher */}
      {isDismissed && !panelOpen && !welcomeOpen && (
        <button
          data-onboarding-resume
          type="button"
          onClick={resume}
          className="fixed bottom-5 right-[72px] z-40 hidden md:flex items-center gap-1.5 px-3 py-2.5 rounded-full bg-surface border border-border shadow-lg text-[11px] font-medium text-text-muted hover:text-text transition-colors"
        >
          <RotateCcw className="w-3 h-3" />
          Devam Et
        </button>
      )}

      {spotlightStep && spotlightMeta && (
        <SpotlightOverlay
          target={spotlightMeta.target ? `[data-onboarding-target="${spotlightMeta.target}"]` : null}
          title={spotlightMeta.title}
          description={spotlightMeta.description}
          stepNumber={spotlightIndex + 1}
          totalSteps={spotlightOrder.length}
          onNext={() => advanceSpotlight(1)}
          onBack={spotlightIndex > 0 ? () => advanceSpotlight(-1) : undefined}
          onLater={endSpotlight}
          onOpenPage={spotlightMeta.route ? () => router.push(spotlightMeta.route as string) : undefined}
        />
      )}
    </>
  );
}
