"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/context/locale-context";

export default function AccessDeniedPage() {
  const router = useRouter();
  const { t } = useLocale();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-danger/10 rounded-2xl mb-5">
          <svg className="w-7 h-7 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M5.073 18.5A9 9 0 1118.927 5.5 9 9 0 015.073 18.5z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-text mb-2">{t("common.accessDenied.title")}</h1>
        <p className="text-sm text-text-muted mb-8">
          {t("common.accessDenied.description")}
        </p>
        <div className="flex flex-col gap-2">
          <Button onClick={() => router.replace("/dashboard")} className="w-full">
            {t("common.navigation.dashboard")}
          </Button>
          <Button onClick={() => router.back()} variant="secondary" className="w-full">
            {t("common.actions.goBack")}
          </Button>
        </div>
      </div>
    </div>
  );
}
