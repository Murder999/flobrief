import Link from "next/link";

interface LockedFeatureProps {
  feature: string;
  children: React.ReactNode;
  allowed: boolean;
}

export function LockedFeature({ feature: _feature, children, allowed }: LockedFeatureProps) {
  if (allowed) return <>{children}</>;

  return (
    <div className="relative">
      <div className="pointer-events-none select-none opacity-30">{children}</div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl bg-black/50 backdrop-blur-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
          <svg
            className="h-5 w-5 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>
        <p className="text-center text-sm font-medium text-white">
          Bu özellik planınızda mevcut değil
        </p>
        <Link
          href="/dashboard/settings/billing"
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
        >
          Planı Yükselt
        </Link>
      </div>
    </div>
  );
}
