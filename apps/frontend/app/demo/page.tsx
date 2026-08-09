"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock3, FlaskConical, ShieldCheck } from "lucide-react";
import { ApiError, demoApi, type DemoPublicStatus } from "@/lib/api-client";

type TurnstileApi = {
  render: (
    container: string | HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
      theme: "auto";
    }
  ) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const FEATURES = [
  "Örnek marka, brief ve içerik takvimi",
  "Onay ve revizyon akışlarını özgürce deneme",
  "Her ziyaretçi için tamamen izole çalışma alanı",
  "Süre sonunda otomatik ve güvenli kapatma",
];

export default function DemoPage() {
  const [demoStatus, setDemoStatus] = useState<DemoPublicStatus | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const widgetId = useRef<string | null>(null);

  useEffect(() => {
    demoApi
      .status()
      .then(setDemoStatus)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Demo durumu alınamadı"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const siteKey = demoStatus?.captcha_site_key;
    if (!demoStatus?.captcha_required || !siteKey) return;

    const renderWidget = () => {
      if (!window.turnstile || widgetId.current) return;
      widgetId.current = window.turnstile.render("#demo-turnstile", {
        sitekey: siteKey,
        theme: "auto",
        callback: setCaptchaToken,
        "expired-callback": () => setCaptchaToken(null),
        "error-callback": () => {
          setCaptchaToken(null);
          setError("Güvenlik doğrulaması yüklenemedi. Lütfen sayfayı yenileyin.");
        },
      });
    };

    const existing = document.querySelector<HTMLScriptElement>(
      'script[src^="https://challenges.cloudflare.com/turnstile/"]'
    );
    if (existing) {
      if (window.turnstile) renderWidget();
      else existing.addEventListener("load", renderWidget, { once: true });
    } else {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      script.addEventListener("load", renderWidget, { once: true });
      document.head.appendChild(script);
    }

    return () => {
      if (widgetId.current && window.turnstile) {
        window.turnstile.remove(widgetId.current);
        widgetId.current = null;
      }
    };
  }, [demoStatus]);

  async function startDemo() {
    if (!demoStatus?.available) return;
    if (demoStatus.captcha_required && !captchaToken) {
      setError("Lütfen güvenlik doğrulamasını tamamlayın.");
      return;
    }
    setStarting(true);
    setError(null);
    try {
      await demoApi.start(captchaToken);
      window.location.assign("/dashboard?demo=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Demo çalışma alanı oluşturulamadı");
      if (widgetId.current) window.turnstile?.reset(widgetId.current);
      setCaptchaToken(null);
      setStarting(false);
    }
  }

  const canStart =
    Boolean(demoStatus?.available) &&
    (!demoStatus?.captcha_required || Boolean(captchaToken)) &&
    !starting;

  return (
    <main className="min-h-screen bg-background relative overflow-hidden">
      <div className="absolute inset-0 hero-grid opacity-30" />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 10%, rgba(99,102,241,0.14), transparent 42%)",
        }}
      />

      <div className="relative max-w-6xl mx-auto px-5 py-8 lg:py-14">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-text-muted hover:text-text transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Ana sayfaya dön
        </Link>

        <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-16 items-center mt-12">
          <section>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-accent/20 bg-accent/8 text-accent text-xs font-semibold mb-6">
              <FlaskConical className="w-3.5 h-3.5" />
              SELF-SERVICE DEMO
            </div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight text-text leading-[1.08]">
              Flobrief&apos;i kendi
              <span className="gradient-text"> çalışma alanınızda </span>
              keşfedin.
            </h1>
            <p className="mt-5 text-lg text-text-muted leading-relaxed max-w-xl">
              Kayıt formu veya kredi kartı olmadan, örnek verilerle hazırlanmış izole bir
              ajans çalışma alanına girin.
            </p>
            <div className="mt-8 grid sm:grid-cols-2 gap-3">
              {FEATURES.map((feature) => (
                <div key={feature} className="flex items-start gap-2.5 text-sm text-text-secondary">
                  <CheckCircle2 className="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
                  {feature}
                </div>
              ))}
            </div>
          </section>

          <section className="bg-surface border border-border rounded-3xl shadow-2xl p-6 md:p-8">
            <div className="w-12 h-12 rounded-2xl bg-accent/10 text-accent flex items-center justify-center mb-5">
              <FlaskConical className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-text">Demo çalışma alanını başlat</h2>
            <p className="text-sm text-text-muted mt-2">
              Oluşturulan veriler diğer ziyaretçilerden tamamen ayrıdır.
            </p>

            {loading ? (
              <div className="space-y-3 mt-7">
                <div className="h-12 bg-surface-2 rounded-xl animate-pulse" />
                <div className="h-12 bg-surface-2 rounded-xl animate-pulse" />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 mt-7">
                  <div className="rounded-xl bg-surface-2 border border-border p-3.5">
                    <Clock3 className="w-4 h-4 text-accent mb-2" />
                    <p className="text-xs text-text-muted">Demo süresi</p>
                    <p className="font-semibold text-text mt-0.5">
                      {demoStatus?.duration_hours ?? "—"} saat
                    </p>
                  </div>
                  <div className="rounded-xl bg-surface-2 border border-border p-3.5">
                    <ShieldCheck className="w-4 h-4 text-success mb-2" />
                    <p className="text-xs text-text-muted">Gizlilik</p>
                    <p className="font-semibold text-text mt-0.5">İzole sandbox</p>
                  </div>
                </div>

                {demoStatus?.captcha_required && (
                  <div className="mt-5 min-h-[65px] flex justify-center">
                    <div id="demo-turnstile" />
                  </div>
                )}

                {error && (
                  <div className="mt-4 rounded-xl border border-danger/20 bg-danger/8 px-4 py-3 text-sm text-danger">
                    {error}
                  </div>
                )}
                {!error && demoStatus && !demoStatus.available && (
                  <div className="mt-4 rounded-xl border border-warning/20 bg-warning/8 px-4 py-3 text-sm text-warning">
                    {demoStatus.unavailable_reason}
                  </div>
                )}

                <button
                  type="button"
                  onClick={startDemo}
                  disabled={!canStart}
                  className="mt-5 w-full h-12 rounded-xl bg-accent text-white font-semibold flex items-center justify-center gap-2 hover:bg-accent-hover transition-all disabled:opacity-45 disabled:cursor-not-allowed"
                >
                  {starting ? "Çalışma alanı hazırlanıyor…" : "Demoyu şimdi başlat"}
                  {!starting && <ArrowRight className="w-4 h-4" />}
                </button>
                <p className="text-[11px] text-text-muted text-center mt-3 leading-relaxed">
                  Dış e-posta, WhatsApp, davet ve ödeme işlemleri demo güvenliği için kapalıdır.
                </p>
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
