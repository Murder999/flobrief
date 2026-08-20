"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  AlertCircle,
  Building2,
  Eye,
  EyeOff,
  Mail,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { authApi, ApiError } from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";
import { EnglishLoginModal } from "./EnglishLoginModal";

const EASE = [0.16, 1, 0.3, 1] as const;
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

type ModalView = "role-selection" | "agency-login" | "brand-login" | "forgot-password";
type Role = "agency" | "brand";

interface RoleCopy {
  badgeLabel: string;
  heading: string;
  subheading: string;
  emailPlaceholder: string;
  forbiddenMessage: string;
  accentIcon: typeof Building2;
}

const ROLE_COPY: Record<Role, RoleCopy> = {
  agency: {
    badgeLabel: "Ajans Hesabı",
    heading: "Ajans hesabınıza giriş yapın",
    subheading: "Markalarınızı, briflerinizi ve ekibinizi yönetin.",
    emailPlaceholder: "siz@ajans.com",
    forbiddenMessage: "Hesabınız devre dışı. Ajans yöneticinizle iletişime geçin.",
    accentIcon: Building2,
  },
  brand: {
    badgeLabel: "Marka Portalı",
    heading: "Marka hesabınıza giriş yapın",
    subheading: "Brieflerinizi takip edin, teslimleri inceleyin ve onaylayın.",
    emailPlaceholder: "siz@marka.com",
    forbiddenMessage: "Hesabınıza erişim yok. Ajansınızla iletişime geçin.",
    accentIcon: Sparkles,
  },
};

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  returnTo?: string;
}

export function LoginModal(props: LoginModalProps) {
  const { locale } = useLocale();
  return locale === "en" ? <EnglishLoginModal {...props} /> : <TurkishLoginModal {...props} />;
}

function TurkishLoginModal({ open, onClose, returnTo }: LoginModalProps) {
  const shouldReduceMotion = useReducedMotion() ?? false;
  const [view, setView] = useState<ModalView>("role-selection");
  const [role, setRole] = useState<Role | null>(null);
  const [direction, setDirection] = useState<1 | -1>(1);

  const containerRef = useRef<HTMLDivElement>(null);
  const firstCardRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Every time the modal opens fresh, start from role selection.
  useEffect(() => {
    if (open) {
      setView("role-selection");
      setRole(null);
      setDirection(1);
    }
  }, [open]);

  // Focus trap, Escape-to-close, body scroll lock, and focus return to trigger.
  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !containerRef.current) return;
      const focusable = Array.from(
        containerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus();
    };
  }, [open, onClose]);

  // Move focus to the right place whenever the visible step changes.
  useEffect(() => {
    if (!open) return;
    const raf = requestAnimationFrame(() => {
      if (view === "role-selection") {
        firstCardRef.current?.focus();
      } else {
        containerRef.current?.querySelector<HTMLInputElement>('input[type="email"]')?.focus();
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [view, open]);

  function selectRole(nextRole: Role) {
    setDirection(1);
    setRole(nextRole);
    setView(nextRole === "agency" ? "agency-login" : "brand-login");
  }

  function backToRoleSelection() {
    setDirection(-1);
    setView("role-selection");
  }

  function openForgotPassword() {
    setDirection(1);
    setView("forgot-password");
  }

  function backToLoginForm() {
    setDirection(-1);
    setView(role === "brand" ? "brand-login" : "agency-login");
  }

  const slideVariants = {
    enter: (dir: 1 | -1) => ({ opacity: 0, x: shouldReduceMotion ? 0 : dir * 24 }),
    center: { opacity: 1, x: 0 },
    exit: (dir: 1 | -1) => ({ opacity: 0, x: shouldReduceMotion ? 0 : dir * -24 }),
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="login-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: shouldReduceMotion ? 0.01 : 0.18 }}
          onClick={onClose}
        >
          <div className="absolute inset-0 bg-background/75 backdrop-blur-sm" />

          <motion.div
            key="login-card"
            ref={containerRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="login-modal-title"
            layout
            className="relative z-10 w-full max-w-sm max-h-[calc(100vh-2rem)] overflow-y-auto"
            initial={{ opacity: 0, scale: 0.95, y: 14 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: shouldReduceMotion ? 0.01 : 0.22, ease: EASE }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-surface border border-border rounded-2xl shadow-[0_32px_80px_rgba(0,0,0,0.2)]">
              {/* Header */}
              <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border/60">
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: "var(--gradient-accent)" }}
                  >
                    <span className="text-white font-bold text-xs">P</span>
                  </div>
                  <span className="text-sm font-semibold text-text tracking-tight">PostPiloter</span>
                </div>
                <button
                  onClick={onClose}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
                  aria-label="Kapat"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body */}
              <div className="px-6 py-5 overflow-hidden">
                <AnimatePresence mode="wait" custom={direction} initial={false}>
                  <motion.div
                    key={view}
                    custom={direction}
                    variants={slideVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    transition={{ duration: shouldReduceMotion ? 0.01 : 0.22, ease: EASE }}
                  >
                    {view === "role-selection" && (
                      <RoleSelection firstCardRef={firstCardRef} onSelect={selectRole} />
                    )}
                    {(view === "agency-login" || view === "brand-login") && (
                      <LoginFormView
                        role={view === "agency-login" ? "agency" : "brand"}
                        onBack={backToRoleSelection}
                        onForgotPassword={openForgotPassword}
                        onLoginSuccess={onClose}
                        returnTo={returnTo}
                      />
                    )}
                    {view === "forgot-password" && <ForgotPasswordView onBack={backToLoginForm} />}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ── Role selection ───────────────────────────────────────────────────────── */

interface RoleSelectionProps {
  firstCardRef: React.RefObject<HTMLButtonElement>;
  onSelect: (role: Role) => void;
}

function RoleSelection({ firstCardRef, onSelect }: RoleSelectionProps) {
  return (
    <div>
      <div className="mb-5">
        <h2 id="login-modal-title" className="text-base font-bold text-text mb-1">
          PostPiloter’a Giriş Yap
        </h2>
        <p className="text-xs text-text-muted">Devam etmek istediğiniz çalışma alanını seçin.</p>
      </div>

      <div className="space-y-2.5 mb-5">
        <button
          ref={firstCardRef}
          type="button"
          onClick={() => onSelect("agency")}
          className="group flex items-center gap-3.5 w-full text-left bg-background border border-border rounded-xl px-4 py-3.5 hover:border-accent/40 hover:bg-accent/4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 transition-all duration-150"
        >
          <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition-colors">
            <Building2 className="w-[18px] h-[18px] text-accent" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text">Ajans Girişi</p>
            <p className="text-xs text-text-muted">Briefleri, markaları, teslimleri ve ekibinizi yönetin.</p>
          </div>
          <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-all flex-shrink-0" />
        </button>

        <button
          type="button"
          onClick={() => onSelect("brand")}
          className="group flex items-center gap-3.5 w-full text-left bg-background border border-border rounded-xl px-4 py-3.5 hover:border-purple/40 hover:bg-purple/4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple/40 transition-all duration-150"
        >
          <div className="w-9 h-9 rounded-xl bg-purple-subtle flex items-center justify-center flex-shrink-0 group-hover:bg-purple/20 transition-colors">
            <Sparkles className="w-[18px] h-[18px] text-purple" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text">Marka Girişi</p>
            <p className="text-xs text-text-muted">Brieflerinizi takip edin, teslimleri inceleyin ve onaylayın.</p>
          </div>
          <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-purple group-hover:translate-x-0.5 transition-all flex-shrink-0" />
        </button>
      </div>

      <div className="text-center">
        <Link href="/auth/register" className="text-xs text-text-muted hover:text-text transition-colors">
          Hesabınız yok mu? <span className="font-medium text-accent">Ücretsiz başlayın</span>
        </Link>
      </div>
    </div>
  );
}

/* ── Login form (shared between agency & brand) ──────────────────────────── */

interface LoginFormViewProps {
  role: Role;
  onBack: () => void;
  onForgotPassword: () => void;
  onLoginSuccess: () => void;
  returnTo?: string;
}

function LoginFormView({ role, onBack, onForgotPassword, onLoginSuccess, returnTo }: LoginFormViewProps) {
  const { login, isLoading } = useAuth();
  const copy = ROLE_COPY[role];
  const AccentIcon = copy.accentIcon;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      // Redirect target is resolved by useAuth().login() itself, based on the
      // authenticated user's actual user_type — the role card is UI copy only.
      await login({ email, password }, returnTo);
      onLoginSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("E-posta veya şifre hatalı. Lütfen kontrol edin.");
        } else if (err.status === 403) {
          setError(copy.forbiddenMessage);
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

  const errorId = `modal-${role}-login-error`;

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-accent transition-colors mb-4"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Geri
      </button>

      <div className="inline-flex items-center gap-2 px-2.5 py-1 bg-accent/8 border border-accent/20 rounded-full mb-3">
        <AccentIcon className="w-3 h-3 text-accent" />
        <span className="text-[11px] font-medium text-accent">{copy.badgeLabel}</span>
      </div>
      <h2 id="login-modal-title" className="text-base font-bold text-text mb-1">
        {copy.heading}
      </h2>
      <p className="text-xs text-text-muted mb-5 leading-relaxed">{copy.subheading}</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-text-muted" htmlFor={`modal-${role}-email`}>
            E-posta adresi
          </label>
          <input
            id={`modal-${role}-email`}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
            placeholder={copy.emailPlaceholder}
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-medium text-text-muted" htmlFor={`modal-${role}-password`}>
              Şifre
            </label>
            <button
              type="button"
              onClick={onForgotPassword}
              className="text-xs text-text-muted hover:text-accent transition-colors"
            >
              Şifremi unuttum
            </button>
          </div>
          <div className="relative">
            <input
              id={`modal-${role}-password`}
              type={showPw ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-background border border-border rounded-xl px-4 py-3 pr-11 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
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

        {error && (
          <div
            role="alert"
            id={errorId}
            className="flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3"
          >
            <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <Button
          type="submit"
          className="w-full"
          isLoading={isLoading}
          aria-describedby={error ? errorId : undefined}
        >
          Giriş Yap
        </Button>
      </form>
    </div>
  );
}

/* ── Forgot password ──────────────────────────────────────────────────────── */

function ForgotPasswordView({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 422) {
        // Deliberately still show the generic "sent" state — matches the
        // standalone /auth/forgot-password page's email-enumeration guard.
        setSent(true);
      } else {
        setError("Geçerli bir e-posta adresi girin.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  if (sent) {
    return (
      <div>
        <div className="w-11 h-11 bg-success/10 border border-success/20 rounded-2xl flex items-center justify-center mb-4">
          <Mail className="w-5 h-5 text-success" />
        </div>
        <h2 id="login-modal-title" className="text-base font-bold text-text mb-1.5">
          E-posta gönderildi
        </h2>
        <p className="text-xs text-text-muted mb-5 leading-relaxed">
          Eğer <strong className="text-text font-medium">{email}</strong> adresiyle kayıtlı bir hesap
          varsa, şifre sıfırlama bağlantısı gönderildi. Spam klasörünüzü de kontrol edin.
        </p>
        <Button type="button" variant="secondary" className="w-full" onClick={onBack}>
          Giriş formuna dön
        </Button>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-accent transition-colors mb-4"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Geri
      </button>

      <div className="mb-5">
        <h2 id="login-modal-title" className="text-base font-bold text-text mb-1">
          Şifremi unuttum
        </h2>
        <p className="text-xs text-text-muted leading-relaxed">
          E-posta adresinizi girin, şifre sıfırlama bağlantısı gönderelim.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-text-muted" htmlFor="modal-fp-email">
            E-posta adresi
          </label>
          <input
            id="modal-fp-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
            placeholder="siz@ornek.com"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3"
          >
            <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <Button type="submit" className="w-full" isLoading={isLoading}>
          Sıfırlama Bağlantısı Gönder
        </Button>
      </form>
    </div>
  );
}
