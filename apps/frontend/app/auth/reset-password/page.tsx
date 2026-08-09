"use client";

import { Button } from "@/components/ui/button";
import { AuthCard } from "@/components/auth/auth-card";
import { authApi, ApiError } from "@/lib/api-client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";
import { AlertCircle, CheckCircle2, XCircle, Eye, EyeOff, ArrowLeft } from "lucide-react";

function ResetPasswordForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get("token") || "";

  const [password,        setPassword]        = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPw,          setShowPw]          = useState(false);
  const [showConfirm,     setShowConfirm]      = useState(false);
  const [isLoading,       setIsLoading]       = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [success,         setSuccess]         = useState(false);

  if (!token) {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-danger/10 border border-danger/20 rounded-2xl flex items-center justify-center mx-auto mb-5">
          <XCircle className="w-6 h-6 text-danger" />
        </div>
        <h2 className="text-xl font-bold text-text mb-2 tracking-tight">Geçersiz Bağlantı</h2>
        <p className="text-sm text-text-muted mb-6 leading-relaxed">
          Bu şifre sıfırlama bağlantısı geçersiz veya süresi dolmuş.
          Lütfen yeni bir bağlantı isteyin.
        </p>
        <Link href="/auth/forgot-password">
          <Button className="w-full">Yeni bağlantı iste</Button>
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-success/10 border border-success/20 rounded-2xl flex items-center justify-center mx-auto mb-5">
          <CheckCircle2 className="w-6 h-6 text-success" />
        </div>
        <h2 className="text-xl font-bold text-text mb-2 tracking-tight">Şifre Güncellendi</h2>
        <p className="text-sm text-text-muted mb-6 leading-relaxed">
          Şifreniz başarıyla güncellendi. Yeni şifrenizle giriş yapabilirsiniz.
        </p>
        <Button className="w-full" onClick={() => router.push("/auth/login")}>
          Giriş Yap
        </Button>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Şifreler eşleşmiyor. Lütfen tekrar kontrol edin.");
      return;
    }
    if (password.length < 8) {
      setError("Şifre en az 8 karakter olmalıdır.");
      return;
    }

    setIsLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setError("Bu bağlantı geçersiz veya süresi dolmuş. Lütfen yeni bağlantı isteyin.");
        } else {
          setError(err.message || "Bir hata oluştu.");
        }
      } else {
        setError("Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <div className="mb-6">
        <Link
          href="/auth/login"
          className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-accent transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Giriş sayfasına dön
        </Link>
        <h1 className="text-2xl font-bold text-text tracking-tight mb-1.5">Yeni Şifre Belirle</h1>
        <p className="text-sm text-text-muted leading-relaxed">
          Güçlü ve benzersiz bir şifre seçin.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* New password */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-text-muted" htmlFor="new-pw">
            Yeni şifre
          </label>
          <div className="relative">
            <input
              id="new-pw"
              type={showPw ? "text" : "password"}
              autoComplete="new-password"
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

        {/* Confirm password */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-text-muted" htmlFor="confirm-pw">
            Yeni şifre tekrar
          </label>
          <div className="relative">
            <input
              id="confirm-pw"
              type={showConfirm ? "text" : "password"}
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full bg-surface border border-border rounded-xl px-4 py-3 pr-11 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
              placeholder="••••••••••"
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowConfirm((p) => !p)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text transition-colors"
              aria-label={showConfirm ? "Şifreyi gizle" : "Şifreyi göster"}
            >
              {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {confirmPassword && password !== confirmPassword && (
            <p className="text-xs text-danger mt-1">Şifreler eşleşmiyor</p>
          )}
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl bg-danger/8 border border-danger/20 px-4 py-3"
          >
            <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <Button type="submit" className="w-full" isLoading={isLoading}>
          Şifremi Güncelle
        </Button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthCard>
      <Suspense
        fallback={
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-surface-2 rounded-lg w-48" />
            <div className="h-4 bg-surface-2 rounded-lg w-64" />
            <div className="h-12 bg-surface-2 rounded-xl" />
            <div className="h-12 bg-surface-2 rounded-xl" />
            <div className="h-12 bg-accent/20 rounded-xl" />
          </div>
        }
      >
        <ResetPasswordForm />
      </Suspense>
    </AuthCard>
  );
}
