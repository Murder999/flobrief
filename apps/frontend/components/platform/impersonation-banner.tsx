"use client";

import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { platformApi } from "@/lib/api-client";
import { impersonationState, platformAuthStorage } from "@/lib/platform-auth";

export function ImpersonationBanner() {
  const router = useRouter();
  const [ending, setEnding] = useState(false);
  const email = useSyncExternalStore(
    impersonationState.subscribe,
    impersonationState.getEmail,
    () => null
  );

  if (!email) return null;

  async function handleEndImpersonation() {
    setEnding(true);
    try {
      const token = platformAuthStorage.getToken();
      if (token) await platformApi.endImpersonation(token);
    } catch {
      // best-effort — the server-side session record still expires on its
      // own short TTL even if this call fails.
    }
    impersonationState.clear();
    router.refresh();
    setEnding(false);
  }

  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2.5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        <span className="text-sm text-amber-300 font-medium">
          Impersonating{" "}
          <span className="font-bold text-amber-200">{email}</span>
        </span>
        <span className="text-xs text-amber-400/70">
          — All actions are logged and visible
        </span>
      </div>
      <button
        onClick={handleEndImpersonation}
        disabled={ending}
        className="text-xs font-semibold px-3 py-1 rounded-md bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40 transition-colors disabled:opacity-50"
      >
        {ending ? "Ending…" : "End Impersonation"}
      </button>
    </div>
  );
}
