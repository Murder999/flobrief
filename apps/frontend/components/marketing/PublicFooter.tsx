import Link from "next/link";
import { ArrowRight } from "lucide-react";

const solutionLinks = [
  { label: "Ajans Programı", href: "/ajans-programi" },
  { label: "Müşteri Onay Sistemi", href: "/musteri-onay-sistemi" },
  { label: "Revizyon Takibi", href: "/revizyon-takip" },
  { label: "Müşteri Portalı", href: "/musteri-portali" },
  { label: "Online Brief", href: "/online-brief" },
] as const;

export function PublicFooter() {
  return (
    <footer className="border-t border-border bg-background" data-testid="public-footer">
      <div className="mx-auto grid max-w-7xl gap-10 px-6 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <Link href="/" className="group mb-4 inline-flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-accent text-sm font-black text-white" aria-hidden="true">
              P
            </span>
            <span className="text-base font-bold tracking-tight text-text group-hover:text-accent">PostPiloter</span>
          </Link>
          <p className="mb-6 max-w-sm text-sm leading-relaxed text-text-muted">
            Ajanslar ve müşterileri için brief, iş, yorum, revizyon ve onay süreçlerini aynı çalışma alanında buluşturan operasyon platformu.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/demo" className="inline-flex min-h-11 items-center gap-1.5 rounded-xl bg-gradient-accent px-4 text-xs font-semibold text-white">
              Demoyu İncele
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
            <Link href="/auth/register" className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-xs font-semibold text-text-secondary hover:border-border-hover hover:text-text">
              Hesap Oluştur
            </Link>
          </div>
        </div>

        <div>
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-text">Çözümler</h2>
          <ul className="space-y-3">
            {solutionLinks.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="text-sm text-text-muted transition-colors hover:text-text">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-text">Başlangıç</h2>
          <ul className="space-y-3">
            <li><Link href="/pricing" className="text-sm text-text-muted hover:text-text">Fiyatlandırma</Link></li>
            <li><Link href="/auth/register" className="text-sm text-text-muted hover:text-text">Ücretsiz Kayıt</Link></li>
            <li><Link href="/auth/agency-login" className="text-sm text-text-muted hover:text-text">Ajans Girişi</Link></li>
            <li><Link href="/brand/login" className="text-sm text-text-muted hover:text-text">Müşteri Girişi</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 sm:flex-row">
          <p className="text-xs text-text-muted">© {new Date().getFullYear()} PostPiloter. Tüm hakları saklıdır.</p>
          <p className="text-xs text-text-muted">Ajans–müşteri kreatif operasyonları için.</p>
        </div>
      </div>
    </footer>
  );
}
