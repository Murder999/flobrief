import type { Locale } from "./config";
import { currentLocale } from "./current";

const COPY: Record<Locale, Record<string, string>> = {
  en: {
    badRequest: "The request could not be completed. Check the information and try again.",
    unauthorized: "Your session has expired. Log in again.",
    forbidden: "You don’t have permission to perform this action.",
    notFound: "The requested item could not be found.",
    conflict: "This change conflicts with an existing record.",
    tooLarge: "The selected file is too large.",
    validation: "Check the highlighted fields and try again.",
    rateLimit: "Too many attempts. Wait a moment and try again.",
    server: "The service is temporarily unavailable. Try again shortly.",
    network: "Check your connection and try again.",
  },
  tr: {
    badRequest: "İşlem tamamlanamadı. Bilgileri kontrol edip tekrar deneyin.",
    unauthorized: "Oturumunuz sona erdi. Lütfen tekrar giriş yapın.",
    forbidden: "Bu işlemi gerçekleştirme yetkiniz yok.",
    notFound: "İstenen kayıt bulunamadı.",
    conflict: "Bu değişiklik mevcut bir kayıtla çakışıyor.",
    tooLarge: "Seçilen dosya çok büyük.",
    validation: "İşaretli alanları kontrol edip tekrar deneyin.",
    rateLimit: "Çok fazla deneme yaptınız. Bir süre bekleyip tekrar deneyin.",
    server: "Hizmet geçici olarak kullanılamıyor. Lütfen kısa süre sonra tekrar deneyin.",
    network: "Bağlantınızı kontrol edip tekrar deneyin.",
  },
};

const TURKISH_MESSAGE = /[çğıöşüÇĞİÖŞÜ]|\b(bu|bir|lütfen|geçersiz|bulunamadı|yetkiniz|başarısız|hata|kullanıcı|davet|şifre|kayıt|işlem)\b/i;

export function localizeApiErrorMessage(
  message: string,
  status: number,
  locale: Locale = currentLocale()
): string {
  const copy = COPY[locale];
  if (status === 401) return copy.unauthorized;
  if (status === 403) return copy.forbidden;
  if (status === 404) return copy.notFound;
  if (status === 409) return copy.conflict;
  if (status === 413) return copy.tooLarge;
  if (status === 429) return copy.rateLimit;
  if (status >= 500) return copy.server;
  if (status === 422 && (message.startsWith("HTTP ") || locale === "en" && TURKISH_MESSAGE.test(message))) {
    return copy.validation;
  }
  if (status === 400 && (message.startsWith("HTTP ") || locale === "en" && TURKISH_MESSAGE.test(message))) {
    return copy.badRequest;
  }
  if (locale === "en" && TURKISH_MESSAGE.test(message)) return copy.badRequest;
  return message || copy.network;
}
