"use client";

import { useEffect, useRef } from "react";
import { useLocale } from "@/context/locale-context";

export interface ConfirmActionDetails {
  action: string;
  agency?: string;
  brand?: string;
  user?: string;
  role?: string;
}

interface ConfirmActionModalProps {
  open: boolean;
  details: ConfirmActionDetails;
  loading?: boolean;
  destructive?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ConfirmActionModal({
  open,
  details,
  loading = false,
  destructive = false,
  onClose,
  onConfirm,
}: ConfirmActionModalProps) {
  const { t } = useLocale();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [loading, onClose, open]);

  if (!open) return null;

  const rows = [
    [t("platform.confirm.action"), details.action],
    [t("platform.confirm.agency"), details.agency],
    [t("platform.confirm.brand"), details.brand],
    [t("platform.confirm.user"), details.user],
    [t("platform.confirm.role"), details.role],
  ].filter((row): row is [string, string] => Boolean(row[1]));

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/65 p-4" role="presentation">
      <section
        aria-labelledby="confirm-action-title"
        aria-modal="true"
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl sm:p-6"
        data-testid="confirm-action-modal"
        role="dialog"
      >
        <div className="mb-5">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-warning">
            PostPiloter Control
          </p>
          <h2 className="text-lg font-semibold text-text" id="confirm-action-title">
            {t("platform.confirm.title")}
          </h2>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            {t("platform.confirm.warning")}
          </p>
        </div>

        <dl className="divide-y divide-border rounded-xl border border-border bg-surface-2 px-4">
          {rows.map(([label, value]) => (
            <div className="flex items-start justify-between gap-4 py-3" key={label}>
              <dt className="text-xs font-medium text-text-muted">{label}</dt>
              <dd className="max-w-[65%] break-words text-right text-sm font-medium text-text">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-2 disabled:opacity-50"
            disabled={loading}
            onClick={onClose}
            ref={cancelRef}
            type="button"
          >
            {t("platform.provision.cancel")}
          </button>
          <button
            className={`rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
              destructive ? "bg-danger hover:bg-danger/85" : "bg-accent hover:bg-accent-hover"
            }`}
            data-testid="confirm-action-submit"
            disabled={loading}
            onClick={onConfirm}
            type="button"
          >
            {loading ? t("platform.provision.creating") : t("platform.confirm.continue")}
          </button>
        </div>
      </section>
    </div>
  );
}
