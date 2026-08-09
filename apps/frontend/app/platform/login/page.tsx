"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, platformAuthApi } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import {
  ShieldCheck,
  Eye,
  EyeOff,
  AlertCircle,
  Building2,
  Users,
  Activity,
  FileText,
  Lock,
  ArrowLeft,
} from "lucide-react";
import { motion } from "framer-motion";

const ES = [0.16, 1, 0.3, 1] as const;

function SystemPreviewCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "text-text-muted",
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-surface-2 border border-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-surface-3 flex items-center justify-center">
          <Icon className="w-3.5 h-3.5 text-text-muted" />
        </div>
        <span className="text-xs text-text-muted">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </div>
  );
}

export default function PlatformLoginPage() {
  const router = useRouter();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await platformAuthApi.login(email, password);
      if (res.mfa_required && res.mfa_session_token) {
        platformAuthStorage.setMfaSession(res.mfa_session_token);
        router.push("/platform/mfa");
        return;
      }
      platformAuthStorage.setToken(res.access_token);
      router.push("/platform/dashboard");
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setError("Sunucuya bağlanılamıyor. Backend servisi çalışıyor mu?");
      } else if (err.status === 401) {
        setError("E-posta veya şifre hatalı. Lütfen tekrar deneyin.");
      } else if (err.status === 403) {
        setError("Bu giriş yalnızca platform yöneticileri içindir.");
      } else if (err.status === 429) {
        setError("Çok fazla başarısız deneme. Lütfen birkaç dakika bekleyin.");
      } else if (err.status === 422) {
        setError("E-posta formatını kontrol edin.");
      } else {
        setError(err.message || `Sunucu hatası (HTTP ${err.status})`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row overflow-hidden">

      {/* ── Left: System preview panel ─────────────────────────────────────── */}
      <motion.div
        className="hidden lg:flex lg:w-[44%] relative flex-col justify-between p-12 overflow-hidden"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: ES }}
      >
        {/* Background */}
        <div className="absolute inset-0 bg-gradient-to-br from-accent/5 via-transparent to-purple/5" />
        <div className="absolute right-0 top-0 bottom-0 w-px bg-border" />
        <div className="absolute -top-32 -left-16 w-[400px] h-[400px] bg-accent/4 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 right-16 w-[300px] h-[300px] bg-purple/3 rounded-full blur-3xl pointer-events-none" />

        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4, ease: ES }}
        >
          <Link href="/" className="inline-flex items-center gap-3 group w-fit">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shadow-glow-sm"
              style={{ background: "var(--gradient-accent)" }}
            >
              <ShieldCheck className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text leading-none">Flobrief</p>
              <p className="text-[10px] text-accent font-semibold tracking-widest uppercase">
                Platform Admin
              </p>
            </div>
          </Link>
        </motion.div>

        {/* System summary */}
        <motion.div
          className="relative space-y-6"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.07, delayChildren: 0.2 } } }}
        >
          <motion.div
            variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20 mb-4">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              <span className="text-xs font-medium text-success-text">Tüm sistemler çalışıyor</span>
            </div>
            <h2 className="text-2xl font-bold text-text leading-tight tracking-tight mb-2">
              Platform Kontrol Merkezi
            </h2>
            <p className="text-sm text-text-muted leading-relaxed max-w-xs">
              Tüm ajansları, kullanıcıları, abonelikleri ve sistem sağlığını
              tek bir panelden yönetin.
            </p>
          </motion.div>

          {/* Mini stat grid */}
          <motion.div
            className="grid grid-cols-2 gap-3"
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            <SystemPreviewCard icon={Building2} label="Ajanslar"     value="—" sub="Canlı kiracılar"  color="text-text" />
            <SystemPreviewCard icon={Users}     label="Kullanıcılar" value="—" sub="Aktif hesaplar"   color="text-text" />
            <SystemPreviewCard icon={Activity}  label="API Durumu"   value="OK" sub="Son 24 saat"     color="text-success" />
            <SystemPreviewCard icon={FileText}  label="Audit Log"    value="—" sub="Son 7 gün"        color="text-text" />
          </motion.div>

          {/* Audit note */}
          <motion.div
            variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.4, delay: 0.1 } } }}
            className="flex items-start gap-3 p-4 bg-surface-2 border border-border rounded-xl"
          >
            <Lock className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
            <p className="text-xs text-text-muted leading-relaxed">
              Tüm yönetici girişleri ve aksiyonlar değiştirilemez audit kayıtlarına işlenir.
              Platform erişimi yalnızca yetkili yöneticilere açıktır.
            </p>
          </motion.div>
        </motion.div>

        <motion.p
          className="relative text-xs text-text-muted"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.4 }}
        >
          © {new Date().getFullYear()} Flobrief Platform
        </motion.p>
      </motion.div>

      {/* ── Right: Login form ───────────────────────────────────────────────── */}
      <motion.div
        className="flex-1 flex flex-col justify-center p-6 lg:p-16 relative"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: ES }}
      >
        <div className="absolute top-0 right-0 w-[500px] h-[400px] bg-accent/3 rounded-full blur-3xl pointer-events-none" />

        {/* Mobile logo */}
        <div className="lg:hidden mb-10 relative">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shadow-glow-sm"
              style={{ background: "var(--gradient-accent)" }}
            >
              <ShieldCheck className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text leading-none">Flobrief</p>
              <p className="text-[10px] text-accent font-semibold tracking-widest uppercase">
                Platform Admin
              </p>
            </div>
          </Link>
        </div>

        <motion.div
          className="relative max-w-[380px] mx-auto w-full"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } } }}
        >
          {/* Header */}
          <motion.div
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
            className="mb-8"
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-warning/8 border border-warning/20 rounded-full mb-4">
              <Lock className="w-3 h-3 text-warning" />
              <span className="text-xs font-medium text-warning-text">Kısıtlı erişim alanı</span>
            </div>
            <h1 className="text-2xl font-bold text-text tracking-tight mb-1.5">
              Yönetici Girişi
            </h1>
            <p className="text-sm text-text-muted">
              Bu alan yalnızca Flobrief platform yöneticileri içindir.
            </p>
          </motion.div>

          {/* Form */}
          <motion.form
            onSubmit={handleSubmit}
            className="space-y-4"
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            {/* Email */}
            <div className="space-y-1.5">
              <label htmlFor="platform-login-email" className="block text-xs font-medium text-text-muted">
                E-posta adresi
              </label>
              <input
                id="platform-login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
                placeholder="admin@flobrief.com"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label htmlFor="platform-login-password" className="block text-xs font-medium text-text-muted">
                Şifre
              </label>
              <div className="relative">
                <input
                  id="platform-login-password"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-surface border border-border rounded-xl px-4 py-3 pr-11 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
                  placeholder="••••••••••"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPw((p) => !p)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text transition-colors"
                  aria-label={showPw ? "Şifreyi gizle" : "Şifreyi göster"}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3"
              >
                <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
                <p className="text-sm text-danger">{error}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold text-white transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ background: "var(--gradient-accent)" }}
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Doğrulanıyor…
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  Güvenli Giriş Yap
                </>
              )}
            </button>
          </motion.form>

          {/* Security note */}
          <motion.div
            variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.4, delay: 0.1 } } }}
            className="mt-6 pt-6 border-t border-border"
          >
            <p className="text-xs text-text-muted text-center leading-relaxed">
              Tüm giriş denemeleri kayıt altına alınır ve izlenir.
              Platform yöneticisi değil misiniz?{" "}
              <Link href="/auth/login" className="text-accent hover:text-accent-hover transition-colors inline-flex items-center gap-1">
                <ArrowLeft className="w-3 h-3" />
                Normal girişe dön
              </Link>
            </p>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
