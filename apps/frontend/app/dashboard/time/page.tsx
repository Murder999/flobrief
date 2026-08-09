"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function TimeIndexPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/time/my");
  }, [router]);
  return null;
}
