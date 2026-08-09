"use client";

import Link from "next/link";
import type { AssetRead } from "@/lib/api-client";
import MediaGallery from "@/components/media/MediaGallery";
import { Folder, ChevronDown } from "lucide-react";

interface BriefAttachmentsSectionProps {
  assets: AssetRead[];
  excludeAssetIds: Set<string>;
  accessToken: string;
}

export function BriefAttachmentsSection({ assets, excludeAssetIds, accessToken }: BriefAttachmentsSectionProps) {
  const referenceAssets = assets.filter((a) => !excludeAssetIds.has(a.id));

  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <Folder className="w-4 h-4 text-accent" />
          <p className="text-sm font-semibold text-text">Brief Dosyaları ve Referansları</p>
        </div>
        <Link
          href="/brand/files"
          className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors font-medium"
        >
          Tüm dosyalar
          <ChevronDown className="w-3 h-3 -rotate-90" />
        </Link>
      </div>
      <div className="p-5">
        <MediaGallery
          assets={referenceAssets}
          accessToken={accessToken}
          emptyMessage="Bu briefe henüz destekleyici dosya eklenmemiş"
        />
      </div>
    </div>
  );
}
