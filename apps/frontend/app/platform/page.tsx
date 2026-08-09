"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { platformAuthStorage } from "@/lib/platform-auth";

export default function PlatformRootPage() {
  const router = useRouter();
  useEffect(() => {
    const token = platformAuthStorage.getToken();
    router.replace(token ? "/platform/dashboard" : "/platform/login");
  }, [router]);
  return null;
}
