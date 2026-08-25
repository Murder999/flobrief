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
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  MessageSquare,
  Users,
  FileText,
  BarChart3,
  Layers,
} from "lucide-react";

const ES = [0.16, 1, 0.3, 1] as const;

/* ── Static product preview scene ────────────────────────────────────────── */

function ProductScene() {
  return (
    <div className="relative w-full max-w-[420px] mx-auto select-none pointer-events-none">
      {/* Ambient light */}
      <div className="absolute -top-20 -left-20 w-72 h-72 bg-accent/8 rounded-full blur-3xl" />
      <div className="absolute -bottom-10 right-0 w-56 h-56 bg-purple/5 rounded-full blur-3xl" />

      <div className="relative space-y-3">
        {/* Mini header bar */}
        <div className="bg-surface border border-border rounded-xl px-4 py-3 flex items-center gap-3 shadow-card">
          <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: "var(--gradient-accent)" }}>
            <span className="text-white text-xs font-bold">P</span>
          </div>
          <span className="text-xs font-medium text-text">PostPiloter — Creative Agency</span>
          <div className="ml-auto flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center">
              <span className="text-[8px] font-bold text-accent">AK</span>
            </div>
            <div className="w-5 h-5 rounded-full bg-surface-2 flex items-center justify-center">
              <span className="text-[8px] font-bold text-text-muted">ME</span>
            </div>
            <div className="w-5 h-5 rounded-full bg-surface-2 flex items-center justify-center">
              <span className="text-[8px] font-bold text-text-muted">SÖ</span>
            </div>
          </div>
        </div>

        {/* Brief cards */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5, ease: ES }}
          className="bg-surface border border-border rounded-xl p-4 shadow-card"
        >
          <div className="flex items-start justify-between mb-2.5">
            <div className="flex items-center gap-2">
              <FileText className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text">Nike Yaz Kampanyası 2025</span>
            </div>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-warning/10 border border-warning/20 rounded-md text-[10px] font-medium text-warning-text">
              <Clock className="w-2.5 h-2.5" />
              Onay Bekliyor
            </span>
          </div>
          <p className="text-[11px] text-text-muted mb-3 leading-relaxed">
            Sosyal medya içerik paketi — 12 post, 4 story, 2 reel
          </p>
          <div className="flex items-center gap-3 text-[10px] text-text-muted">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              15 Tem
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              3 yorum
            </span>
            <div className="ml-auto flex -space-x-1">
              {["AK", "ME", "SÖ"].map((i) => (
                <div key={i} className="w-4 h-4 rounded-full bg-accent/20 border border-surface flex items-center justify-center">
                  <span className="text-[7px] font-bold text-accent">{i[0]}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5, ease: ES }}
          className="bg-surface border border-border rounded-xl p-4 shadow-card"
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <FileText className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs font-semibold text-text">Adidas Q3 Lansman Briefingi</span>
            </div>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-success/10 border border-success/20 rounded-md text-[10px] font-medium text-success-text">
              <CheckCircle2 className="w-2.5 h-2.5" />
              Onaylandı
            </span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-text-muted">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              20 Tem
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              7 yorum
            </span>
          </div>
        </motion.div>

        {/* Mini calendar strip */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.5, ease: ES }}
          className="bg-surface border border-border rounded-xl p-4 shadow-card"
        >
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-semibold text-text">İçerik Takvimi — Temmuz</span>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center">
            {["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pa"].map((d) => (
              <div key={d} className="text-[9px] text-text-muted font-medium pb-1">{d}</div>
            ))}
            {[14, 15, 16, 17, 18, 19, 20].map((day) => (
              <div
                key={day}
                className={`text-[10px] py-1 rounded-md font-medium ${
                  day === 15
                    ? "bg-accent text-white"
                    : day === 17 || day === 20
                    ? "bg-warning/20 text-warning"
                    : "text-text-muted"
                }`}
              >
                {day}
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-3 text-[10px] text-text-muted">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-accent inline-block" />
              Yayın günü
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-warning inline-block" />
              Onay deadline
            </span>
          </div>
        </motion.div>

        {/* Floating notification */}
        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 1.0, duration: 0.45, ease: ES }}
          className="absolute -right-4 top-1/2 -translate-y-4 bg-surface border border-border rounded-xl p-3 shadow-modal w-52 z-10"
        >
          <div className="flex items-start gap-2.5">
            <div className="w-6 h-6 rounded-full bg-success/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <CheckCircle2 className="w-3 h-3 text-success" />
            </div>
            <div>
              <p className="text-xs font-medium text-text leading-tight">Brief onaylandı</p>
              <p className="text-[10px] text-text-muted mt-0.5">Adidas — Zeynep Demir</p>
              <p className="text-[9px] text-text-muted opacity-60 mt-1">2 dakika önce</p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

/* ── Feature list ─────────────────────────────────────────────────────────── */

const FEATURES = [
  { icon: FileText,  text: "Brief yönetimi ve onay akışları" },
  { icon: Calendar,  text: "İçerik takvimi ve planlama" },
  { icon: Layers,    text: "White-label marka portalleri" },
  { icon: Users,     text: "Ekip iş birliği ve görev takibi" },
  { icon: BarChart3, text: "Raporlama ve analitik" },
];

/* ── Login form ───────────────────────────────────────────────────────────── */

function AgencyLoginForm() {
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
          setError("Hesabınız devre dışı. Ajans yöneticinizle iletişime geçin.");
        } else if (err.status === 429) {
          setError("Çok fazla başarısız deneme. Birkaç dakika bekleyin.");
        } else if (err.status === 0 || err.status >= 500) {
          setError("Sunucuya bağlanılamıyor. Lütfen daha sonra tekrar deneyin.");
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

      {/* ── Left: Form ──────────────────────────────────────────────────────── */}
      <motion.div
        className="flex-1 flex flex-col justify-center p-6 lg:px-16 lg:py-12 relative order-1"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: ES }}
      >
        <div className="absolute top-0 left-0 w-[500px] h-[400px] bg-accent/4 rounded-full blur-3xl pointer-events-none" />

        <motion.div
          className="relative max-w-[400px] mx-auto w-full lg:mx-0"
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
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-accent/8 border border-accent/20 rounded-full mb-4">
              <Building2 className="w-3 h-3 text-accent" />
              <span className="text-xs font-medium text-accent">Ajans Hesabı</span>
            </div>
            <h1 className="text-2xl font-bold text-text tracking-tight mb-2">
              Ajans paneline giriş yapın
            </h1>
            <p className="text-sm text-text-muted leading-relaxed">
              Brief&apos;lerinizi, markalarınızı, ekip görevlerini ve onay süreçlerini
              tek çalışma alanından yönetin.
            </p>
          </motion.div>

          {/* Form fields */}
          <motion.form
            onSubmit={handleSubmit}
            className="space-y-4"
            variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            {/* Email */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-text-muted" htmlFor="agency-email">
                E-posta adresi
              </label>
              <input
                id="agency-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
                placeholder="siz@ajans.com"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-text-muted" htmlFor="agency-password">
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
                  id="agency-password"
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
                id="agency-login-error"
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
              aria-describedby={error ? "agency-login-error" : undefined}
            >
              Ajans Paneline Giriş Yap
            </Button>
          </motion.form>

          {/* Footer links */}
          <motion.div
            variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.4, delay: 0.1 } } }}
            className="mt-6 space-y-3"
          >
            <p className="text-center text-sm text-text-muted">
              Hesabınız yok mu?{" "}
              <Link href="/auth/register" className="text-accent hover:text-accent-hover font-medium transition-colors">
                Ücretsiz başlayın
              </Link>
            </p>
            <div className="text-center">
              <Link
                href="/brand/login"
                className="text-xs text-text-muted hover:text-text transition-colors"
              >
                Marka hesabıyla mı giriyorsunuz?{" "}
                <span className="underline underline-offset-2">Marka girişi</span>
              </Link>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>

      {/* ── Right: Product scene ─────────────────────────────────────────────── */}
      <motion.div
        className="hidden lg:flex lg:w-[52%] relative flex-col items-center justify-center p-12 overflow-hidden order-2"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.55, ease: ES }}
      >
        {/* Background */}
        <div className="absolute inset-0 bg-gradient-to-bl from-accent/5 via-transparent to-purple/4" />
        <div className="absolute left-0 top-0 bottom-0 w-px bg-border" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />
        <div className="absolute -bottom-40 -right-20 w-[400px] h-[400px] bg-purple/5 rounded-full blur-3xl pointer-events-none" />

        <div className="relative w-full max-w-[440px]">
          {/* Tagline */}
          <motion.div
            className="mb-8"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5, ease: ES }}
          >
            <ul className="space-y-2.5">
              {FEATURES.map(({ icon: Icon, text }, i) => (
                <motion.li
                  key={text}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.35 + i * 0.05, duration: 0.4, ease: ES }}
                  className="flex items-center gap-2.5 text-xs text-text-muted"
                >
                  <div className="w-5 h-5 rounded-full bg-accent/15 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-2.5 h-2.5 text-accent" />
                  </div>
                  {text}
                </motion.li>
              ))}
            </ul>
          </motion.div>

          {/* Product scene */}
          <ProductScene />
        </div>
      </motion.div>
    </div>
  );
}

export default function AgencyLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "var(--gradient-accent)" }}
            >
              <span className="text-white font-bold text-sm">P</span>
            </div>
            <svg className="w-4 h-4 animate-spin text-text-muted" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        </div>
      }
    >
      <AgencyLoginForm />
    </Suspense>
  );
}
