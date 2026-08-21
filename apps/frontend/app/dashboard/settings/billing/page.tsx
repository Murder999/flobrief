"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  billingApi,
  planApi,
  type SubscriptionRead,
  type InvoiceRead,
  type UsageSummary,
  type PlanRead,
  type CheckoutResponse,
} from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { EntitlementBar } from "@/components/billing/entitlement-bar";
import { PlanCard } from "@/components/billing/plan-card";
import { useToast } from "@/components/ui/toast";

const STATUS_LABELS: Record<string, string> = {
  trialing: "Deneme",
  active: "Aktif",
  past_due: "Ödeme Gecikmiş",
  cancelled: "İptal Edildi",
  expired: "Süresi Doldu",
};

const STATUS_COLORS: Record<string, string> = {
  trialing: "text-amber-400 bg-amber-400/10",
  active: "text-emerald-400 bg-emerald-400/10",
  past_due: "text-red-400 bg-red-400/10",
  cancelled: "text-gray-400 bg-gray-400/10",
  expired: "text-gray-400 bg-gray-400/10",
};

function formatCents(cents: number, currency: string): string {
  const locale = currency === "TRY" ? "tr-TR" : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR");
}

function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse rounded bg-surface-2"
          style={{ width: `${70 + i * 10}%` }}
        />
      ))}
    </div>
  );
}

function SandboxBanner({ response }: { response: CheckoutResponse }) {
  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-300">
      <p className="font-semibold">Sandbox Modu</p>
      <p className="mt-1 text-amber-400/80">
        iyzico API anahtarları yapılandırılmamış. Gerçek ödeme sayfası yerine simüle edilmiş
        oturum oluşturuldu (token: {response.token}).
      </p>
    </div>
  );
}

function BillingPageInner() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const searchParams = useSearchParams();
  const router = useRouter();
  const agencyId = activeAgency?.id ?? null;
  const { confirm, toast } = useToast();

  const [subscription, setSubscription] = useState<SubscriptionRead | null>(null);
  const [invoices, setInvoices] = useState<InvoiceRead[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "upgrade" | "invoices">("overview");
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sandboxResponse, setSandboxResponse] = useState<CheckoutResponse | null>(null);
  const [yearly, setYearly] = useState(false);

  useEffect(() => {
    const upgradePlanId = searchParams.get("upgrade");
    if (upgradePlanId) {
      setTab("upgrade");
      setYearly(searchParams.get("yearly") === "true");
    }
  }, [searchParams]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    try {
      const [sub, inv, sum, allPlans] = await Promise.allSettled([
        billingApi.getSubscription(accessToken, agencyId),
        billingApi.listInvoices(accessToken, agencyId),
        billingApi.getEntitlements(accessToken, agencyId),
        planApi.list(),
      ]);
      if (sub.status === "fulfilled") setSubscription(sub.value);
      if (inv.status === "fulfilled") setInvoices(inv.value);
      if (sum.status === "fulfilled") setUsage(sum.value);
      if (allPlans.status === "fulfilled") setPlans(allPlans.value);
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpgrade(plan: PlanRead) {
    if (!accessToken || !agencyId) return;
    if (plan.monthly_price_cents === 0) {
      window.location.href = "mailto:sales@postpiloter.com?subject=Enterprise Plan";
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const resp = await billingApi.createCheckout(
        { plan_id: plan.id, yearly },
        accessToken,
        agencyId
      );
      if (resp.sandbox) {
        setSandboxResponse(resp);
      } else {
        window.location.href = resp.payment_page_url;
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Bir hata oluştu");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!accessToken || !agencyId) return;
    const ok = await confirm({
      title: "Aboneliği İptal Et",
      message: "Aboneliğinizi iptal etmek istediğinizden emin misiniz? Mevcut döneminiz sonuna kadar erişiminiz devam eder.",
      confirmLabel: "İptal Et",
      destructive: true,
    });
    if (!ok) return;
    setActionLoading(true);
    setError(null);
    try {
      await billingApi.cancelSubscription(accessToken, agencyId);
      toast("Abonelik iptal edildi.", "success");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "İptal edilemedi");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard lines={4} />
        <SkeletonCard lines={5} />
        <SkeletonCard lines={3} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
          <svg
            className="h-4 w-4 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {error}
        </div>
      )}

      {sandboxResponse && <SandboxBanner response={sandboxResponse} />}

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
        {(["overview", "upgrade", "invoices"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-all ${
              tab === t
                ? "bg-surface-2 text-text"
                : "text-text-muted hover:text-text"
            }`}
          >
            {t === "overview"
              ? "Genel Bakış"
              : t === "upgrade"
                ? "Plan Değiştir"
                : "Faturalar"}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-6">
          {/* Current plan card */}
          <div className="rounded-2xl border border-border bg-surface p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm text-text-muted">Mevcut Plan</p>
                <h2 className="mt-1 text-2xl font-bold text-text">
                  {subscription?.plan.name ?? "Plan Yok"}
                </h2>
                {subscription && (
                  <span
                    className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      STATUS_COLORS[subscription.status] ??
                      "text-text-muted bg-surface-2"
                    }`}
                  >
                    {STATUS_LABELS[subscription.status] ?? subscription.status}
                  </span>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-2">
                <svg
                  className="h-5 w-5 text-text-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                  />
                </svg>
              </div>
            </div>

            {subscription && (
              <div className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-text-muted">Dönem Başlangıcı</p>
                  <p className="mt-0.5 font-medium text-text">
                    {formatDate(subscription.current_period_start)}
                  </p>
                </div>
                <div>
                  <p className="text-text-muted">Dönem Bitişi</p>
                  <p className="mt-0.5 font-medium text-text">
                    {formatDate(subscription.current_period_end)}
                  </p>
                </div>
                <div>
                  <p className="text-text-muted">Sağlayıcı</p>
                  <p className="mt-0.5 font-medium capitalize text-text">
                    {subscription.billing_provider}
                  </p>
                </div>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={() => setTab("upgrade")}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Plan Değiştir
              </button>
              {subscription?.status === "active" && (
                <button
                  onClick={handleCancel}
                  disabled={actionLoading}
                  className="rounded-xl border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-60"
                >
                  Aboneliği İptal Et
                </button>
              )}
            </div>
          </div>

          {/* Usage */}
          {usage && (
            <div className="rounded-2xl border border-border bg-surface p-6">
              <div className="flex items-center gap-2 mb-5">
                <svg
                  className="h-4 w-4 text-text-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  />
                </svg>
                <h3 className="font-semibold text-text">Kullanım</h3>
              </div>
              <div className="space-y-5">
                <EntitlementBar
                  label="Markalar"
                  used={usage.brands.used}
                  limit={usage.brands.limit}
                />
                <EntitlementBar
                  label="Kullanıcılar"
                  used={usage.users.used}
                  limit={usage.users.limit}
                />
                <EntitlementBar
                  label="Brief Şablonları"
                  used={usage.brief_templates.used}
                  limit={usage.brief_templates.limit}
                />
                <EntitlementBar
                  label="Depolama (GB)"
                  used={usage.storage_gb.used}
                  limit={usage.storage_gb.limit}
                />
              </div>
            </div>
          )}

          {!subscription && (
            <div className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
              <svg
                className="mx-auto h-8 w-8 text-text-muted/40"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                />
              </svg>
              <p className="mt-3 text-sm text-text-muted">
                Aktif abonelik bulunamadı.
              </p>
              <button
                onClick={() => setTab("upgrade")}
                className="mt-4 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Bir Plan Seç
              </button>
            </div>
          )}
        </div>
      )}

      {tab === "upgrade" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-text-muted">
              Değiştirmek istediğiniz planı seçin.
            </p>
            <div className="flex items-center rounded-xl border border-border bg-surface p-1">
              <button
                onClick={() => setYearly(false)}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                  !yearly ? "bg-surface-2 text-text" : "text-text-muted"
                }`}
              >
                Aylık
              </button>
              <button
                onClick={() => setYearly(true)}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                  yearly ? "bg-surface-2 text-text" : "text-text-muted"
                }`}
              >
                Yıllık −20%
              </button>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {plans
              .filter((p) =>
                ["starter_agency", "pro_agency", "agency_plus", "enterprise"].includes(
                  p.code
                )
              )
              .map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  yearly={yearly}
                  currentPlanId={subscription?.plan_id}
                  onSelect={handleUpgrade}
                  loading={actionLoading}
                />
              ))}
          </div>

          <p className="text-center text-xs text-text-muted">
            Ödeme iyzico tarafından işlenir. Kart bilgileriniz Flobrief sunucularında
            saklanmaz.
          </p>
        </div>
      )}

      {tab === "invoices" && (
        <div className="rounded-2xl border border-border bg-surface">
          <div className="flex items-center gap-2 border-b border-border px-6 py-4">
            <svg
              className="h-4 w-4 text-text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="font-semibold text-text">Faturalar</h3>
          </div>

          {invoices.length === 0 ? (
            <div className="p-10 text-center">
              <svg
                className="mx-auto h-8 w-8 text-text-muted/40"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <p className="mt-3 text-sm text-text-muted">
                Henüz fatura oluşturulmamış.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-muted">
                  <th className="px-6 py-3 font-medium">Tarih</th>
                  <th className="px-6 py-3 font-medium">Tutar</th>
                  <th className="px-6 py-3 font-medium">Durum</th>
                  <th className="px-6 py-3 font-medium">Dönem</th>
                  <th className="px-6 py-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="px-6 py-4 text-text">{formatDate(inv.created_at)}</td>
                    <td className="px-6 py-4 font-medium text-text">
                      {formatCents(inv.amount_cents, inv.currency)}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          inv.status === "paid"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : inv.status === "open"
                              ? "bg-amber-500/10 text-amber-400"
                              : "bg-gray-500/10 text-gray-400"
                        }`}
                      >
                        {inv.status === "paid"
                          ? "Ödendi"
                          : inv.status === "open"
                            ? "Bekliyor"
                            : inv.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-text-muted">
                      {formatDate(inv.period_start)} — {formatDate(inv.period_end)}
                    </td>
                    <td className="px-6 py-4">
                      {inv.hosted_invoice_url && (
                        <a
                          href={inv.hosted_invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          Görüntüle
                          <svg
                            className="h-3 w-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                            />
                          </svg>
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BillingPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text">Abonelik & Faturalama</h1>
        <p className="mt-1 text-sm text-text-muted">
          Planınızı yönetin, kullanımınızı takip edin ve faturalarınıza erişin.{" "}
          <Link
            href="/pricing"
            className="text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Tüm planları karşılaştır →
          </Link>
        </p>
      </div>
      <Suspense
        fallback={
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-32 animate-pulse rounded-2xl border border-border bg-surface"
              />
            ))}
          </div>
        }
      >
        <BillingPageInner />
      </Suspense>
    </div>
  );
}
