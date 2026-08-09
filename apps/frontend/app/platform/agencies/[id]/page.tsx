"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import {
  ApiError,
  platformApi,
  type PlatformAgencyDetail,
  type ImpersonationResponse,
} from "@/lib/api-client";
import { impersonationState, platformAuthStorage } from "@/lib/platform-auth";

function InfoRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex items-start gap-4 py-3 border-b border-gray-800">
      <span className="text-xs font-medium text-gray-500 w-40 flex-shrink-0 pt-0.5 uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-gray-200 break-all">{value ?? "—"}</span>
    </div>
  );
}

export default function PlatformAgencyDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const agencyId = params.id;

  const [agency, setAgency] = useState<PlatformAgencyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");
  const [showSuspend, setShowSuspend] = useState(false);
  const [impersonateUserId, setImpersonateUserId] = useState("");
  const [impersonateReason, setImpersonateReason] = useState("");
  const [showImpersonate, setShowImpersonate] = useState(false);
  const [impersonateResult, setImpersonateResult] = useState<ImpersonationResponse | null>(null);

  useEffect(() => {
    async function load() {
      const token = platformAuthStorage.getToken();
      if (!token) { router.replace("/platform/login"); return; }
      try {
        const data = await platformApi.getAgency(agencyId, token);
        setAgency(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          platformAuthStorage.clearAll();
          router.replace("/platform/login");
        } else {
          setError(err instanceof ApiError ? err.message : "Failed to load");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [agencyId, router]);

  async function handleSuspend() {
    if (!agency || !suspendReason.trim()) return;
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setActionLoading(true);
    try {
      await platformApi.suspendAgency(agency.id, suspendReason, token);
      setAgency({ ...agency, status: "suspended" });
      setShowSuspend(false);
      setSuspendReason("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReactivate() {
    if (!agency) return;
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setActionLoading(true);
    try {
      await platformApi.reactivateAgency(agency.id, token);
      setAgency({ ...agency, status: "active" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleImpersonate() {
    if (!impersonateUserId.trim() || !impersonateReason.trim()) return;
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setActionLoading(true);
    try {
      const result = await platformApi.startImpersonation(
        impersonateUserId.trim(),
        impersonateReason.trim(),
        token
      );
      setImpersonateResult(result);
      impersonationState.setActive(result.impersonated_email);
      setShowImpersonate(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impersonation failed");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-6 w-32 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-4 bg-gray-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !agency) {
    return (
      <div className="p-8">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <p className="text-red-400 font-medium">{error}</p>
          <Link href="/platform/agencies" className="mt-3 text-sm text-gray-400 hover:text-gray-100 inline-block">
            ← Back to agencies
          </Link>
        </div>
      </div>
    );
  }

  if (!agency) return null;

  const mrrFormatted =
    agency.monthly_price_cents != null
      ? `$${(agency.monthly_price_cents / 100).toFixed(0)}/mo`
      : null;

  return (
    <div className="p-8">
      {/* Back */}
      <Link
        href="/platform/agencies"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-6"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        All Agencies
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">{agency.name}</h1>
          <p className="text-sm text-gray-500 mt-1">{agency.slug}</p>
        </div>
        <div className="flex items-center gap-3">
          {agency.status === "active" ? (
            <>
              <button
                onClick={() => setShowImpersonate(true)}
                className="px-4 py-2 rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 text-sm font-medium hover:bg-indigo-600/30 transition-colors"
              >
                Impersonate User
              </button>
              <button
                onClick={() => setShowSuspend(true)}
                className="px-4 py-2 rounded-lg bg-red-600/10 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-600/20 transition-colors"
              >
                Suspend
              </button>
            </>
          ) : (
            <button
              onClick={handleReactivate}
              disabled={actionLoading}
              className="px-4 py-2 rounded-lg bg-emerald-600/10 border border-emerald-500/30 text-emerald-400 text-sm font-medium hover:bg-emerald-600/20 transition-colors disabled:opacity-50"
            >
              {actionLoading ? "Reactivating…" : "Reactivate"}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {impersonateResult && (
        <div className="mb-6 bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-300">
            Impersonating <strong>{impersonateResult.impersonated_email}</strong>
          </p>
          <p className="text-xs text-amber-400/70 mt-1">
            Token is active. Use the impersonation banner to end the session.
          </p>
        </div>
      )}

      {/* Info */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Agency Details</h3>
          <InfoRow label="ID" value={agency.id} />
          <InfoRow label="Name" value={agency.name} />
          <InfoRow label="Slug" value={agency.slug} />
          <InfoRow label="Status" value={agency.status} />
          <InfoRow label="Members" value={agency.member_count} />
          <InfoRow label="Brands" value={agency.brand_count} />
          <InfoRow label="Created" value={new Date(agency.created_at).toLocaleString("en-US")} />
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Subscription</h3>
          <InfoRow label="Plan" value={agency.plan_name} />
          <InfoRow label="Plan Code" value={agency.plan_code} />
          <InfoRow label="Sub Status" value={agency.subscription_status} />
          <InfoRow label="MRR" value={mrrFormatted} />
        </div>
      </div>

      {/* Suspend Modal */}
      {showSuspend && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl">
            <h3 className="text-base font-semibold text-gray-100 mb-1">Suspend Agency</h3>
            <p className="text-sm text-gray-400 mb-5">
              This will block all users of <span className="font-medium text-gray-200">{agency.name}</span> from accessing the platform.
            </p>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Reason (required)</label>
            <textarea
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
              rows={3}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-red-500 resize-none"
            />
            <div className="flex gap-3 mt-5">
              <button onClick={() => setShowSuspend(false)} className="flex-1 py-2.5 rounded-lg border border-gray-700 text-sm text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors">Cancel</button>
              <button
                onClick={handleSuspend}
                disabled={!suspendReason.trim() || actionLoading}
                className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white text-sm font-semibold transition-colors"
              >
                {actionLoading ? "Suspending…" : "Suspend"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Impersonate Modal */}
      {showImpersonate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl">
            <h3 className="text-base font-semibold text-gray-100 mb-1">Impersonate User</h3>
            <p className="text-sm text-gray-400 mb-5">
              This action is logged and visible. You will receive a temporary token to act as the target user.
            </p>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">User ID (UUID)</label>
            <input
              value={impersonateUserId}
              onChange={(e) => setImpersonateUserId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-indigo-500 mb-4"
            />
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Reason (required)</label>
            <textarea
              value={impersonateReason}
              onChange={(e) => setImpersonateReason(e.target.value)}
              rows={2}
              placeholder="Support ticket #123, debugging issue…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500 resize-none"
            />
            <div className="flex gap-3 mt-5">
              <button onClick={() => setShowImpersonate(false)} className="flex-1 py-2.5 rounded-lg border border-gray-700 text-sm text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors">Cancel</button>
              <button
                onClick={handleImpersonate}
                disabled={!impersonateUserId.trim() || !impersonateReason.trim() || actionLoading}
                className="flex-1 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-semibold transition-colors"
              >
                {actionLoading ? "Starting…" : "Start Impersonation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
