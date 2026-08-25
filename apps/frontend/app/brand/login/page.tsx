"use client";

import { Suspense, type FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PostPiloterLogo } from "@/components/brand/PostPiloterLogo";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api-client";
import { isSafeReturnTo } from "@/lib/auth";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  AlertCircle,
  Eye,
  EyeOff,
  Sparkles,
  CheckCircle2,
  Clock,
  MessageSquare,
  RotateCcw,
  FileText,
  Calendar,
  Paperclip,
} from "lucide-react";

const ES = [0.16, 1, 0.3, 1] as const;

/* ── Approval-focused product scene ──────────────────────────────────────── */

function ApprovalScene() {
  return (
    <div className="relative w-full max-w-[380px] mx-auto select-none pointer-events-none">
      <div className="absolute -top-16 left-1/2 -translate-x-1/2 w-64 h-64 bg-purple/6 rounded-full blur-3xl" />
      <div className="absolute bottom-0 right-0 w-48 h-48 bg-accent/4 rounded-full blur-3xl" />

      <div className="relative space-y-3">
        {/* Approval request card */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5, ease: ES }}
          className="bg-surface border border-border rounded-xl p-5 shadow-card"
        >
          {/* Brand header */}
          <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border">
            <div className="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center flex-shrink-0">
              <span className="text-sm font-bold text-accent">N</span>
            </div>
            <div>
              <p className="text-xs font-semibold text-text">Nike Türkiye</p>
              <p className="text-[10px] text-text-muted">Creative Agency · İstanbul</p>
            </div>
            <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 bg-warning/10 border border-warning/20 rounded-md text-[10px] font-medium text-warning-text">
              <Clock className="w-2.5 h-2.5" />
              Onay Bekliyor
            </span>
          </div>

          {/* File preview */}
          <div className="bg-surface-2 border border-border rounded-lg p-3 mb-3">
            <div className="flex items-center gap-2.5 mb-2">
              <Paperclip className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-medium text-text">Nike_YazKampanya_v3.pdf</span>
            </div>
            <div className="h-16 bg-gradient-to-br from-accent/5 to-purple/5 border border-border/50 rounded-md flex items-center justify-center">
              <FileText className="w-6 h-6 text-text-muted opacity-40" />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <div className="flex-1 py-1.5 bg-success/10 border border-success/20 rounded-lg flex items-center justify-center gap-1.5 text-[10px] font-medium text-success-text">
              <CheckCircle2 className="w-3 h-3" />
              Onayla
            </div>
            <div className="flex-1 py-1.5 bg-danger/8 border border-danger/15 rounded-lg flex items-center justify-center gap-1.5 text-[10px] font-medium text-danger-text">
              <RotateCcw className="w-3 h-3" />
              Revizyon İste
            </div>
          </div>
        </motion.div>

        {/* Comments thread */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5, ease: ES }}
          className="bg-surface border border-border rounded-xl p-4 shadow-card"
        >
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs font-semibold text-text">Yorumlar</span>
            <span className="ml-auto text-[10px] text-text-muted">3 yorum</span>
          </div>
          <div className="space-y-2.5">
            <div className="flex items-start gap-2">
              <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[8px] font-bold text-accent">CA</span>
              </div>
              <div className="flex-1 bg-surface-2 rounded-lg px-2.5 py-1.5">
                <p className="text-[10px] font-medium text-text">Creative Agency</p>
                <p className="text-[9px] text-text-muted mt-0.5">3. sayfa düzenlemesi yapıldı, lütfen onaylayın.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-5 h-5 rounded-full bg-warning/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[8px] font-bold text-warning">NK</span>
              </div>
              <div className="flex-1 bg-surface-2 rounded-lg px-2.5 py-1.5">
                <p className="text-[10px] font-medium text-text">Nike Marka</p>
                <p className="text-[9px] text-text-muted mt-0.5">Renk paleti biraz daha koyu olabilir mi?</p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Calendar entry */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.45, ease: ES }}
          className="bg-surface border border-border rounded-xl p-4 shadow-card"
        >
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-semibold text-text">Yayın Takvimi</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-accent/10 border border-accent/20 rounded-xl flex flex-col items-center justify-center flex-shrink-0">
              <span className="text-[9px] text-accent font-medium leading-none">TEM</span>
              <span className="text-base font-bold text-accent leading-tight">15</span>
            </div>
            <div>
              <p className="text-xs font-medium text-text">Kampanya başlangıcı</p>
              <p className="text-[10px] text-text-muted mt-0.5">Instagram + Twitter ilk yayın</p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

/* ── Login form ───────────────────────────────────────────────────────────── */

function BrandLoginForm() {
  const { login, isLoading } = useAuth();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get("returnTo") ?? searchParams.get("redirect") ?? "";

  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [showPw,   setShowPw]   = useState(false);
  const [error,    setError]    = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      await login(
        { email, password },
        isSafeReturnTo(returnTo) ? returnTo : undefined,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("E-posta veya şifre hatalı. Lütfen kontrol edin.");
        } else if (err.status === 403) {
          setError("Hesabınıza erişim yok. Ajansınızla iletişime geçin.");
        } else if (err.status === 429) {
          setError("Çok fazla deneme yapıldı. Birkaç dakika bekleyin.");
        } else if (err.status === 0 || err.status >= 500) {
          setError("Sunucuya bağlanılamıyor. Daha sonra tekrar deneyin.");
        } else {
          setError(err.message || "Giriş başarısız oldu.");
        }
      } else {
        setError("Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.");
      }
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row overflow-hidden">

      {/* ── Left: Product scene ─────────────────────────────────────────────── */}
      <motion.div
        className="hidden lg:flex lg:w-[50%] relative flex-col items-center justify-center p-12 overflow-hidden order-2 lg:order-1"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.55, ease: ES }}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-purple/5 via-transparent to-accent/4" />
        <div className="absolute right-0 top-0 bottom-0 w-px bg-border" />
        <div className="absolute -top-32 left-16 w-[350px] h-[350px] bg-accent/4 rounded-full blur-3xl pointer-events-none" />

        <div className="relative w-full max-w-[400px]">
          <motion.div
            className="mb-8"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.5, ease: ES }}
          >
            <h2 className="text-lg font-bold text-text mb-2 tracking-tight">
              Onay süreçlerinizi takip edin
            </h2>
            <p className="text-sm text-text-muted leading-relaxed max-w-xs">
              Ajansınızdan gelen işleri inceleyin, yorum bırakın,
              revizyon isteyin veya onaylayın.
            </p>
          </motion.div>
          <ApprovalScene />
        </div>
      </motion.div>

      {/* ── Right: Form ─────────────────────────────────────────────────────── */}
      <motion.div
        className="flex-1 flex flex-col justify-center p-6 lg:px-16 lg:py-12 relative order-1 lg:order-2"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: ES }}
      >
        <div className="absolute top-0 right-0 w-[500px] h-[400px] bg-purple/4 rounded-full blur-3xl pointer-events-none" />

        <motion.div
          className="relative max-w-[400px] mx-auto w-full lg:mx-0 lg:ml-auto"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } } }}
        >
          {/* Logo */}
          <motion.div
            variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
            className="mb-10"
          >
            <Link href="/" className="inline-flex items-center gap-2.5 group">
              <PostPiloterLogo className="h-8 w-auto transition-transform group-hover:scale-[1.02]" priority />
            </Link>
          </motion.div>

          {/* Heading */}
          <motion.div
            variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
            className="mb-7"
          >
            <Link
              href="/auth/login"
              className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-accent transition-colors mb-4"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Giriş seçimine dön
            </Link>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-purple-subtle border border-purple/20 rounded-full mb-4">
              <Sparkles className="w-3 h-3 text-purple" />
              <span className="text-xs font-medium text-purple-text">Marka Portalı</span>
            </div>
            <h1 className="text-2xl font-bold text-text tracking-tight mb-2">
              Marka portalına giriş yapın
            </h1>
            <p className="text-sm text-text-muted leading-relaxed">
              Onay bekleyen işleri, dosya versiyonlarını, yorumları ve
              yayın takviminizi tek yerden takip edin.
            </p>
          </motion.div>

          {/* Return to context */}
          {returnTo && (
            <motion.div
              variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.3 } } }}
              className="mb-4 px-4 py-3 bg-accent/8 border border-accent/20 rounded-xl"
            >
              <p className="text-xs text-accent">
                Devam etmek için marka hesabınızla giriş yapın.
              </p>
            </motion.div>
          )}

          {/* Form */}
          <motion.form
            onSubmit={handleSubmit}
            className="space-y-4"
            variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            {/* Email */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-text-muted" htmlFor="brand-email">
                E-posta adresi
              </label>
              <input
                id="brand-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
                placeholder="siz@marka.com"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-text-muted" htmlFor="brand-password">
                  Şifre
                </label>
                <Link
                  href="/auth/forgot-password"
                  className="text-xs text-text-muted hover:text-accent transition-colors"
                >
                  Şifremi unuttum
                </Link>
              </div>
              <div className="relative">
                <input
                  id="brand-password"
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
                id="brand-login-error"
                className="flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3"
              >
                <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" aria-hidden="true" />
                <p className="text-sm text-danger">{error}</p>
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              className="w-full"
              isLoading={isLoading}
              aria-describedby={error ? "brand-login-error" : undefined}
            >
              Marka Portalına Giriş Yap
            </Button>
          </motion.form>

          {/* Footer */}
          <motion.div
            variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.4, delay: 0.1 } } }}
            className="mt-6 pt-5 border-t border-border space-y-3"
          >
            <p className="text-xs text-text-muted text-center">
              Davet linkinizle mi geldiniz?{" "}
              <Link href="/auth/accept-invite" className="text-accent hover:text-accent-hover transition-colors font-medium">
                Daveti kabul edin
              </Link>
            </p>
            <p className="text-xs text-text-muted text-center">
              Ajans hesabıyla mı giriyorsunuz?{" "}
              <Link href="/auth/agency-login" className="text-text hover:text-accent transition-colors underline underline-offset-2">
                Ajans girişi
              </Link>
            </p>
          </motion.div>
        </motion.div>

        <p className="mt-8 text-center text-xs text-text-muted relative">
          © {new Date().getFullYear()} PostPiloter. Tüm hakları saklıdır.
        </p>
      </motion.div>
    </div>
  );
}

export default function BrandLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: "var(--gradient-accent)" }}
            >
              <span className="text-white font-bold text-xs">P</span>
            </div>
            <svg className="w-4 h-4 animate-spin text-text-muted" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-70" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        </div>
      }
    >
      <BrandLoginForm />
    </Suspense>
  );
}
