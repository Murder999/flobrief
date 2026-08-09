"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PhoneNumberInput } from "@/components/forms/PhoneNumberInput";
import { AuthCard } from "@/components/auth/auth-card";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

const PASSWORD_HINTS = [
  "En az 10 karakter",
  "Büyük ve küçük harf",
  "En az bir rakam",
  "En az bir özel karakter (!@#$%^&*)",
];

export default function RegisterPage() {
  const { register, isLoading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasPhone = phone.length > 0;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPhoneError(null);

    if (password !== confirmPassword) {
      setError("Şifreler eşleşmiyor");
      return;
    }

    // Validate phone format if provided
    if (phone && !/^\+[1-9]\d{6,14}$/.test(phone)) {
      setPhoneError("Geçerli bir telefon numarası girin.");
      return;
    }

    try {
      await register({
        email,
        full_name: fullName,
        password,
        phone_number: phone || null,
        whatsapp_opt_in: phone ? whatsappOptIn : false,
      });
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError("Bu e-posta adresi zaten kayıtlı");
        } else if (err.status === 422) {
          setError("Lütfen tüm alanları doğru doldurun");
        } else {
          setError(err.message);
        }
      } else {
        setError("Bir hata oluştu. Lütfen tekrar deneyin.");
      }
    }
  }

  if (success) {
    return (
      <AuthCard>
        <div className="text-center">
          <div className="w-12 h-12 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-text mb-2">Hesabınız oluşturuldu</h2>
          <p className="text-sm text-text-muted mb-6">
            <strong className="text-text">{email}</strong> adresine bir doğrulama e-postası gönderdik.
            Hesabınızı aktifleştirmek için e-postanızdaki bağlantıya tıklayın.
          </p>
          <Button variant="secondary" className="w-full" onClick={() => router.push("/auth/login")}>
            Giriş sayfasına git
          </Button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text">Hesap Oluştur</h1>
          <p className="mt-1 text-sm text-text-muted">
            14 gün ücretsiz deneyin. Kredi kartı gerekmez.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Ad Soyad"
            type="text"
            placeholder="Adınız Soyadınız"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            autoComplete="name"
          />

          <Input
            label="E-posta"
            type="email"
            placeholder="siz@ajans.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />

          <PhoneNumberInput
            id="register-phone"
            label="Telefon Numarası"
            value={phone}
            onChange={(e164) => {
              setPhone(e164);
              setPhoneError(null);
              if (!e164) setWhatsappOptIn(false);
            }}
            defaultCountry="TR"
            error={phoneError ?? undefined}
            helperText="Onay, revize ve yorum bildirimlerini WhatsApp'tan almak için kullanılır."
          />

          {/* WhatsApp opt-in */}
          <div
            className={`flex items-start gap-3 rounded-xl border px-4 py-3 transition-colors ${
              hasPhone
                ? "border-border bg-surface-2"
                : "border-border/40 bg-surface-2/40 opacity-50"
            }`}
          >
            <div className="relative flex items-center justify-center mt-0.5 flex-shrink-0">
              <input
                type="checkbox"
                id="whatsapp_opt_in"
                checked={whatsappOptIn}
                disabled={!hasPhone}
                onChange={(e) => setWhatsappOptIn(e.target.checked)}
                className="sr-only peer"
              />
              <div
                onClick={() => hasPhone && setWhatsappOptIn((v) => !v)}
                className={`w-4 h-4 rounded border-2 flex items-center justify-center cursor-pointer transition-colors ${
                  whatsappOptIn && hasPhone
                    ? "bg-accent border-accent"
                    : "bg-surface border-border"
                } ${!hasPhone ? "cursor-not-allowed" : ""}`}
              >
                {whatsappOptIn && hasPhone && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            </div>
            <label
              htmlFor="whatsapp_opt_in"
              className={`text-sm cursor-pointer select-none ${hasPhone ? "text-text" : "text-text-muted cursor-not-allowed"}`}
              onClick={() => hasPhone && setWhatsappOptIn((v) => !v)}
            >
              WhatsApp üzerinden bildirim almak istiyorum.
              <span className="block text-xs text-text-muted mt-0.5 leading-relaxed">
                Brief onayı, revize talebi, yorum ve teslim tarihi gibi önemli bildirimler için kullanılır.
                {!hasPhone && (
                  <span className="block mt-0.5 italic">Etkinleştirmek için telefon numarası girin.</span>
                )}
              </span>
            </label>
          </div>

          <Input
            label="Şifre"
            type="password"
            placeholder="••••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />

          <Input
            label="Şifre Tekrar"
            type="password"
            placeholder="••••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
          />

          <div className="bg-surface-2 rounded-lg px-4 py-3">
            <p className="text-xs font-medium text-text-muted mb-2">Şifre gereksinimleri:</p>
            <ul className="space-y-1">
              {PASSWORD_HINTS.map((hint) => (
                <li key={hint} className="flex items-center gap-2 text-xs text-text-muted">
                  <span className="w-1 h-1 bg-text-muted rounded-full flex-shrink-0" />
                  {hint}
                </li>
              ))}
            </ul>
          </div>

          {error && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3">
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}

          <Button type="submit" className="w-full" isLoading={isLoading}>
            Hesap Oluştur
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-text-muted">
          Zaten hesabınız var mı?{" "}
          <Link href="/auth/login" className="text-accent hover:text-accent-hover font-medium">
            Giriş yapın
          </Link>
        </p>

        <p className="mt-4 text-center text-xs text-text-muted">
          Kayıt olarak{" "}
          <span className="text-text-muted underline cursor-pointer">Kullanım Koşulları</span>
          {" "}ve{" "}
          <span className="text-text-muted underline cursor-pointer">Gizlilik Politikası</span>
          {" "}kabul edersiniz.
        </p>
      </>
    </AuthCard>
  );
}
