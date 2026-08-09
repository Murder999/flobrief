"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, platformAuthApi } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";

export default function PlatformMfaPage() {
  const router = useRouter();
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (!platformAuthStorage.getMfaSession()) {
      router.replace("/platform/login");
    }
  }, [router]);

  function handleDigit(index: number, value: string) {
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...code];
    next[index] = digit;
    setCode(next);
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (text.length === 6) {
      setCode(text.split(""));
      inputRefs.current[5]?.focus();
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const mfaSession = platformAuthStorage.getMfaSession();
    if (!mfaSession) {
      router.replace("/platform/login");
      return;
    }
    setLoading(true);
    try {
      const res = recoveryMode
        ? await platformAuthApi.mfaRecovery(mfaSession, recoveryCode.trim())
        : await platformAuthApi.mfaVerify(mfaSession, code.join(""));
      platformAuthStorage.setToken(res.access_token);
      platformAuthStorage.clearMfaSession();
      router.push("/platform/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-indigo-600 rounded-xl mb-5">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-100">Two-Factor Auth</h1>
          <p className="text-sm text-gray-400 mt-1.5">
            {recoveryMode
              ? "Enter one of your recovery codes"
              : "Enter the 6-digit code from your authenticator app"}
          </p>
        </div>

        <form onSubmit={handleVerify} className="space-y-6">
          {recoveryMode ? (
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Recovery Code
              </label>
              <input
                type="text"
                value={recoveryCode}
                onChange={(e) => setRecoveryCode(e.target.value)}
                placeholder="XXXXXX-YYYYYY"
                required
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-3 text-center">
                Authentication Code
              </label>
              <div className="flex gap-2 justify-center" onPaste={handlePaste}>
                {code.map((digit, i) => (
                  <input
                    key={i}
                    ref={(el) => { inputRefs.current[i] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleDigit(i, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    className="w-11 h-14 text-center text-xl font-bold bg-gray-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                  />
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2.5">
              <svg className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || (!recoveryMode && code.join("").length < 6)}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/40 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Verifying…
              </span>
            ) : (
              "Verify"
            )}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => { setRecoveryMode(!recoveryMode); setError(null); }}
            className="text-xs text-gray-500 hover:text-indigo-400 transition-colors"
          >
            {recoveryMode ? "← Back to authenticator code" : "Use a recovery code instead"}
          </button>
        </div>

        <div className="mt-4 text-center">
          <button
            onClick={() => { platformAuthStorage.clearMfaSession(); router.push("/platform/login"); }}
            className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
          >
            Cancel and go back
          </button>
        </div>
      </div>
    </div>
  );
}
