"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { getRedirectAfterLogin } from "@/lib/auth";
import { Building2, Sparkles, ArrowRight } from "lucide-react";

const ES = [0.16, 1, 0.3, 1] as const;

export default function LoginSelectPage() {
  const { user, isInitialized, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isInitialized || isLoading) return;
    if (user) router.replace(getRedirectAfterLogin(user.user_type));
  }, [isInitialized, isLoading, user, router]);

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 relative overflow-hidden">
      <div className="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-accent/6 rounded-full blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-1/4 w-[300px] h-[300px] bg-purple/5 rounded-full blur-3xl" />

      <motion.div
        className="relative w-full max-w-sm"
        initial="hidden"
        animate="visible"
        variants={{ visible: { transition: { staggerChildren: 0.07 } } }}
      >
        {/* Logo */}
        <motion.div
          variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          className="flex flex-col items-center mb-8"
        >
          <Link href="/" className="group flex flex-col items-center gap-3">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-glow"
              style={{ background: "var(--gradient-accent)" }}
            >
              <span className="text-white font-bold text-xl">F</span>
            </div>
            <span className="text-2xl font-semibold text-text tracking-tight group-hover:text-accent transition-colors">
              Flobrief
            </span>
          </Link>
        </motion.div>

        {/* Heading */}
        <motion.div
          variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          className="text-center mb-7"
        >
          <h1 className="text-xl font-bold text-text mb-1.5">Giriş yapın</h1>
          <p className="text-sm text-text-muted">Hesap türünüzü seçerek devam edin.</p>
        </motion.div>

        <div className="space-y-3 mb-6">
          <motion.div
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            <Link
              href="/auth/agency-login"
              className="group flex items-center gap-4 w-full bg-surface border border-border rounded-2xl px-5 py-4 hover:border-accent/40 hover:shadow-card-hover transition-all duration-200 relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-accent/0 group-hover:from-accent/4 to-transparent transition-all duration-300 pointer-events-none" />
              <div className="relative w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition-colors">
                <Building2 className="w-5 h-5 text-accent" />
              </div>
              <div className="relative flex-1 min-w-0">
                <p className="text-sm font-semibold text-text">Ajans Girişi</p>
                <p className="text-xs text-text-muted mt-0.5">Brief yönetimi ve ekip iş birliği</p>
              </div>
              <ArrowRight className="relative w-4 h-4 text-text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-all flex-shrink-0" />
            </Link>
          </motion.div>

          <motion.div
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: ES } } }}
          >
            <Link
              href="/brand/login"
              className="group flex items-center gap-4 w-full bg-surface border border-border rounded-2xl px-5 py-4 hover:border-purple/40 hover:shadow-card-hover transition-all duration-200 relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-purple/0 group-hover:from-purple/4 to-transparent transition-all duration-300 pointer-events-none" />
              <div className="relative w-10 h-10 rounded-xl bg-purple-subtle flex items-center justify-center flex-shrink-0 group-hover:bg-purple/20 transition-colors">
                <Sparkles className="w-5 h-5 text-purple" />
              </div>
              <div className="relative flex-1 min-w-0">
                <p className="text-sm font-semibold text-text">Marka Girişi</p>
                <p className="text-xs text-text-muted mt-0.5">Brief inceleme ve onay portalı</p>
              </div>
              <ArrowRight className="relative w-4 h-4 text-text-muted group-hover:text-purple group-hover:translate-x-0.5 transition-all flex-shrink-0" />
            </Link>
          </motion.div>
        </div>

        <motion.div
          variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.35 } } }}
          className="text-center mb-5"
        >
          <Link href="/auth/register" className="text-sm text-text-muted hover:text-text transition-colors">
            Hesabınız yok mu?{" "}
            <span className="font-medium text-accent">Ücretsiz başlayın</span>
          </Link>
        </motion.div>

        <motion.div
          variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.35 } } }}
          className="pt-4 border-t border-border text-center"
        >
          <Link
            href="/platform/login"
            className="text-xs text-text-muted/60 hover:text-text-muted transition-colors"
          >
            Platform yöneticisi misiniz?{" "}
            <span className="underline underline-offset-2">Yönetici girişi</span>
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
}
