"use client";

import { useState } from "react";
import { ApiError, mfaApi } from "@/lib/api-client";

interface MfaSetupCardProps {
  accessToken: string | null;
  mfaEnabled: boolean;
  onChanged: () => void;
}

type Stage = "idle" | "qr" | "confirm" | "recovery_shown" | "disable";

export function MfaSetupCard({ accessToken, mfaEnabled, onChanged }: MfaSetupCardProps) {
  const [stage, setStage] = useState<Stage>("idle");
  const [secret, setSecret] = useState<string | null>(null);
  const [otpauthUrl, setOtpauthUrl] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleBeginSetup() {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const res = await mfaApi.setup(accessToken);
      setSecret(res.secret);
      setOtpauthUrl(res.otpauth_url);
      setStage("qr");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "MFA kurulumu başlatılamadı.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!accessToken || code.length !== 6) return;
    setLoading(true);
    setError(null);
    try {
      const res = await mfaApi.confirm(code, accessToken);
      setRecoveryCodes(res.recovery_codes);
      setStage("recovery_shown");
      setCode("");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Kod doğrulanamadı.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDisable() {
    if (!accessToken || code.length !== 6) return;
    setLoading(true);
    setError(null);
    try {
      await mfaApi.disable(code, accessToken);
      setStage("idle");
      setCode("");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "MFA devre dışı bırakılamadı.");
    } finally {
      setLoading(false);
    }
  }

  if (mfaEnabled && stage !== "disable" && stage !== "recovery_shown") {
    return (
      <div className="bg-surface border border-border rounded-2xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-text mb-1">İki Faktörlü Kimlik Doğrulama (MFA)</h3>
            <p className="text-xs text-text-muted">MFA aktif — hesabınız ek koruma altında.</p>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-success/10 text-success flex-shrink-0">
            Aktif
          </span>
        </div>
        <button
          onClick={() => setStage("disable")}
          className="mt-4 text-xs text-danger hover:underline"
        >
          MFA&apos;yı devre dışı bırak
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-2xl p-6">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text mb-1">İki Faktörlü Kimlik Doğrulama (MFA)</h3>
          <p className="text-xs text-text-muted">
            {stage === "disable"
              ? "Devre dışı bırakmak için authenticator uygulamanızdaki güncel kodu girin."
              : "Hesap güvenliğinizi artırmak için etkinleştirin."}
          </p>
        </div>
        {stage === "idle" && (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-warning/10 text-warning flex-shrink-0">
            Devre Dışı
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger">{error}</div>
      )}

      {stage === "idle" && (
        <button
          onClick={handleBeginSetup}
          disabled={loading}
          className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 disabled:opacity-50 transition-colors"
        >
          {loading ? "Başlatılıyor…" : "MFA'yı Etkinleştir"}
        </button>
      )}

      {stage === "qr" && secret && (
        <div className="space-y-4">
          <p className="text-xs text-text-muted">
            Authenticator uygulamanıza (Google Authenticator, 1Password vb.) bu anahtarı manuel ekleyin, ardından 6 haneli kodu girin.
          </p>
          <div className="bg-surface-2 border border-border rounded-lg px-4 py-3">
            <p className="text-xs text-text-muted mb-1">Gizli anahtar</p>
            <code className="text-sm font-mono text-accent break-all">{secret}</code>
          </div>
          {otpauthUrl && (
            <p className="text-xs text-text-muted opacity-60 break-all">{otpauthUrl}</p>
          )}
          <div className="flex items-center gap-2">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6 haneli kod"
              inputMode="numeric"
              className="w-40 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-mono text-center text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
            <button
              onClick={handleConfirm}
              disabled={loading || code.length !== 6}
              className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 disabled:opacity-50 transition-colors"
            >
              {loading ? "Doğrulanıyor…" : "Doğrula ve Etkinleştir"}
            </button>
          </div>
        </div>
      )}

      {stage === "recovery_shown" && (
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-success/10 border border-success/20 text-sm text-success">
            MFA etkinleştirildi. Aşağıdaki kurtarma kodlarını güvenli bir yerde saklayın — bir daha gösterilmeyecek.
          </div>
          <div className="grid grid-cols-2 gap-2">
            {recoveryCodes.map((c) => (
              <code key={c} className="text-xs font-mono bg-surface-2 border border-border rounded-lg px-3 py-2 text-text">{c}</code>
            ))}
          </div>
          <button
            onClick={() => setStage("idle")}
            className="text-xs text-accent hover:underline"
          >
            Tamamlandı
          </button>
        </div>
      )}

      {stage === "disable" && (
        <div className="flex items-center gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="6 haneli kod"
            inputMode="numeric"
            className="w-40 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-mono text-center text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
          />
          <button
            onClick={handleDisable}
            disabled={loading || code.length !== 6}
            className="px-4 py-2 bg-danger text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-colors"
          >
            {loading ? "İşleniyor…" : "Devre Dışı Bırak"}
          </button>
          <button onClick={() => { setStage("idle"); setCode(""); setError(null); }} className="text-xs text-text-muted hover:text-text">
            Vazgeç
          </button>
        </div>
      )}
    </div>
  );
}
