"use client";

import { useEffect } from "react";

export function LandingTitleSync({ title }: { title: string }) {
  useEffect(() => {
    const syncTitle = () => {
      if (document.title !== title) document.title = title;
    };

    syncTitle();
    const observer = new MutationObserver(syncTitle);
    observer.observe(document.head, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => observer.disconnect();
  }, [title]);

  return null;
}
