"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale } from "@/context/locale-context";

function InviteRedirectLoading() {
  const { t } = useLocale();
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <p className="text-sm text-text-muted" role="status">
        {t("auth.invite.loading")}
      </p>
    </main>
  );
}

function LegacyInviteRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    router.replace(token ? `/invite/${encodeURIComponent(token)}` : "/");
  }, [router, searchParams]);

  return <InviteRedirectLoading />;
}

export default function LegacyAcceptInvitePage() {
  return (
    <Suspense fallback={<InviteRedirectLoading />}>
      <LegacyInviteRedirect />
    </Suspense>
  );
}
