"use client";

import { useEffect } from "react";

export function LandingTitleSync({ title }: { title: string }) {
  useEffect(() => {
    if (document.title !== title) document.title = title;
  }, [title]);

  return null;
}
