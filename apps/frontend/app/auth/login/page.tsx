"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LoginModal } from "@/components/auth/LoginModal";
import { useAuth } from "@/hooks/useAuth";
import { getRedirectAfterLogin } from "@/lib/auth";

function LoginPopupRoute() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isInitialized, isLoading } = useAuth();
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!isInitialized || isLoading || !user) return;
    router.replace(getRedirectAfterLogin(user.user_type));
  }, [isInitialized, isLoading, router, user]);

  function closeLogin() {
    setOpen(false);
    router.replace("/");
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[400px] w-[600px] -translate-x-1/2 rounded-full bg-accent/6 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-1/4 h-[300px] w-[300px] rounded-full bg-purple/5 blur-3xl" />
      <div className="flex flex-col items-center gap-3" aria-hidden="true">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-accent shadow-glow">
          <span className="text-xl font-bold text-white">P</span>
        </div>
        <span className="text-2xl font-semibold tracking-tight text-text">PostPiloter</span>
      </div>
      <LoginModal
        open={open}
        onClose={closeLogin}
        returnTo={searchParams.get("redirect") ?? undefined}
      />
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <LoginPopupRoute />
    </Suspense>
  );
}
