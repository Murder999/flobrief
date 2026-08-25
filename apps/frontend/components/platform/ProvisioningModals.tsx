"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocale } from "@/context/locale-context";
import {
  ApiError,
  platformApi,
  type PlanRead,
  type PlatformAgencyCreateResponse,
  type PlatformAgencyRead,
  type PlatformBrandCreateResponse,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { ConfirmActionModal } from "./ConfirmActionModal";

type MembershipMode = "invite" | "attach" | "none";

const fieldClass =
  "w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-text outline-none transition-colors placeholder:text-text-placeholder focus:border-accent";

function ModalFrame({
  title,
  steps,
  activeStep,
  children,
  onClose,
}: {
  title: string;
  steps: string[];
  activeStep: number;
  children: ReactNode;
  onClose: () => void;
}) {
  const { t } = useLocale();
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/65 p-0 sm:items-center sm:p-4">
      <section
        aria-labelledby="provisioning-modal-title"
        aria-modal="true"
        className="flex max-h-[94vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl border border-border bg-surface shadow-2xl sm:rounded-2xl"
        data-testid="provisioning-modal"
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-accent">PostPiloter Control</p>
            <h2 className="text-xl font-semibold text-text" id="provisioning-modal-title">{title}</h2>
          </div>
          <button
            aria-label={t("platform.provision.cancel")}
            className="rounded-lg p-2 text-text-muted hover:bg-surface-2 hover:text-text"
            onClick={onClose}
            type="button"
          >
            <span aria-hidden="true" className="text-xl leading-none">×</span>
          </button>
        </header>
        <ol className="grid border-b border-border bg-surface-2" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
          {steps.map((step, index) => (
            <li
              className={`border-b-2 px-2 py-3 text-center text-[11px] font-semibold sm:text-xs ${
                index === activeStep ? "border-accent text-accent" : index < activeStep ? "border-success text-success" : "border-transparent text-text-muted"
              }`}
              key={step}
            >
              <span className="mr-1 hidden sm:inline">{index + 1}.</span>{step}
            </li>
          ))}
        </ol>
        <div className="overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
      </section>
    </div>
  );
}

function ModePicker({
  value,
  onChange,
  email,
  onEmail,
  labels,
}: {
  value: MembershipMode;
  onChange: (value: MembershipMode) => void;
  email: string;
  onEmail: (value: string) => void;
  labels: { invite: string; attach: string; none: string; email: string };
}) {
  const { t } = useLocale();
  return (
    <div className="space-y-4">
      <div className="grid gap-2">
        {(["invite", "attach", "none"] as const).map((mode) => (
          <label className={`flex cursor-pointer gap-3 rounded-xl border p-3.5 ${value === mode ? "border-accent bg-accent/5" : "border-border bg-surface-2"}`} key={mode}>
            <input checked={value === mode} className="mt-0.5 accent-accent" name="membership-mode" onChange={() => onChange(mode)} type="radio" />
            <span>
              <span className="block text-sm font-medium text-text">{labels[mode]}</span>
              {mode !== "none" && (
                <span className="mt-0.5 block text-xs leading-5 text-text-muted">
                  {mode === "invite" ? t("platform.provision.inviteHelp") : t("platform.provision.attachHelp")}
                </span>
              )}
            </span>
          </label>
        ))}
      </div>
      {value !== "none" && (
        <label className="block text-xs font-medium text-text-muted">
          {labels.email}
          <input
            autoComplete="email"
            className={`${fieldClass} mt-1.5`}
            onChange={(event) => onEmail(event.target.value)}
            placeholder="name@company.com"
            required
            type="email"
            value={email}
          />
        </label>
      )}
    </div>
  );
}

function Footer({
  step,
  lastStep,
  loading,
  onBack,
  onNext,
  onCancel,
}: {
  step: number;
  lastStep: number;
  loading: boolean;
  onBack: () => void;
  onNext: () => void;
  onCancel: () => void;
}) {
  const { t } = useLocale();
  return (
    <div className="mt-6 flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:justify-between">
      <button className="rounded-lg px-4 py-2.5 text-sm font-medium text-text-muted hover:bg-surface-2" onClick={step === 0 ? onCancel : onBack} type="button">
        {step === 0 ? t("platform.provision.cancel") : t("platform.provision.back")}
      </button>
      <button
        className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        data-testid="provisioning-next"
        disabled={loading}
        onClick={onNext}
        type="button"
      >
        {loading ? t("platform.provision.creating") : step === lastStep ? t("platform.provision.create") : t("platform.provision.next")}
      </button>
    </div>
  );
}

export function AgencyProvisioningModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (result: PlatformAgencyCreateResponse) => void;
}) {
  const { locale, t } = useLocale();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"active" | "suspended">("active");
  const [language, setLanguage] = useState<"en" | "tr">(locale);
  const [mode, setMode] = useState<MembershipMode>("invite");
  const [email, setEmail] = useState("");
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [planId, setPlanId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmAttach, setConfirmAttach] = useState(false);

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    platformApi.listPlans(token).then((items) => {
      const active = items.filter((item) => item.is_active);
      setPlans(active);
      setPlanId(active[0]?.id ?? "");
    }).catch((err) => setError(err instanceof ApiError ? err.message : t("platform.provision.required")));
  }, [t]);

  const steps = [t("platform.provision.organization"), t("platform.provision.owner"), t("platform.provision.plan"), t("platform.provision.review")];

  function canContinue() {
    if (step === 0) return name.trim().length >= 2;
    if (step === 1) return mode === "none" || email.trim().includes("@");
    if (step === 2) return Boolean(planId);
    return true;
  }

  async function submit() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await platformApi.createAgency({
        name: name.trim(), status, plan_id: planId, locale: language,
        owner_mode: mode, owner_email: mode === "none" ? null : email.trim(),
        confirm_existing_user: mode === "attach",
      }, token);
      onCreated(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("platform.provision.required"));
    } finally {
      setLoading(false);
      setConfirmAttach(false);
    }
  }

  function next() {
    if (!canContinue()) { setError(t("platform.provision.required")); return; }
    setError(null);
    if (step < 3) setStep(step + 1);
    else if (mode === "attach") setConfirmAttach(true);
    else void submit();
  }

  return (
    <>
      <ModalFrame activeStep={step} onClose={onClose} steps={steps} title={t("platform.provision.agencyTitle")}>
        {error && <div className="mb-4 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
        {step === 0 && <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-medium text-text-muted sm:col-span-2">{t("platform.provision.agencyName")}<input autoFocus className={`${fieldClass} mt-1.5`} data-testid="agency-name" onChange={(e) => setName(e.target.value)} value={name} /></label>
          <label className="text-xs font-medium text-text-muted">{t("platform.provision.status")}<select className={`${fieldClass} mt-1.5`} onChange={(e) => setStatus(e.target.value as typeof status)} value={status}><option value="active">{t("platform.provision.active")}</option><option value="suspended">{t("platform.provision.suspended")}</option></select></label>
          <label className="text-xs font-medium text-text-muted">{t("platform.provision.language")}<select className={`${fieldClass} mt-1.5`} onChange={(e) => setLanguage(e.target.value as typeof language)} value={language}><option value="tr">{t("platform.provision.turkish")}</option><option value="en">{t("platform.provision.english")}</option></select></label>
        </div>}
        {step === 1 && <ModePicker email={email} labels={{ invite: t("platform.provision.inviteOwner"), attach: t("platform.provision.attachOwner"), none: t("platform.provision.noOwner"), email: t("platform.provision.ownerEmail") }} onChange={setMode} onEmail={setEmail} value={mode} />}
        {step === 2 && <div className="space-y-3"><p className="rounded-xl border border-accent/20 bg-accent/5 p-3 text-sm leading-6 text-text-secondary">{t("platform.provision.manualPlan")}</p><div className="grid gap-2 sm:grid-cols-2">{plans.map((plan) => <label className={`cursor-pointer rounded-xl border p-4 ${planId === plan.id ? "border-accent bg-accent/5" : "border-border bg-surface-2"}`} key={plan.id}><input checked={planId === plan.id} className="mr-2 accent-accent" name="plan" onChange={() => setPlanId(plan.id)} type="radio" /><span className="font-medium text-text">{plan.name}</span><span className="mt-1 block text-xs text-text-muted">{plan.currency} {(plan.monthly_price_cents / 100).toFixed(2)} / {t("platform.provision.perMonth")}</span></label>)}</div></div>}
        {step === 3 && <dl className="divide-y divide-border rounded-xl border border-border bg-surface-2 px-4"><ReviewRow label={t("platform.provision.agencyName")} value={name} /><ReviewRow label={t("platform.provision.status")} value={status} /><ReviewRow label={t("platform.provision.summaryOwner")} value={mode === "none" ? t("platform.provision.none") : `${mode}: ${email}`} /><ReviewRow label={t("platform.provision.plan")} value={plans.find((plan) => plan.id === planId)?.name ?? "—"} /></dl>}
        <Footer lastStep={3} loading={loading} onBack={() => setStep(Math.max(0, step - 1))} onCancel={onClose} onNext={next} step={step} />
      </ModalFrame>
      <ConfirmActionModal details={{ action: t("platform.confirm.attach"), agency: name, user: email, role: "owner" }} loading={loading} onClose={() => setConfirmAttach(false)} onConfirm={() => void submit()} open={confirmAttach} />
    </>
  );
}

export function BrandProvisioningModal({
  agencies,
  onClose,
  onCreated,
}: {
  agencies: PlatformAgencyRead[];
  onClose: () => void;
  onCreated: (result: PlatformBrandCreateResponse) => void;
}) {
  const { locale, t } = useLocale();
  const [step, setStep] = useState(0);
  const [agencyId, setAgencyId] = useState(agencies[0]?.id ?? "");
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"active" | "suspended" | "archived">("active");
  const [language, setLanguage] = useState<"en" | "tr">(locale);
  const [mode, setMode] = useState<MembershipMode>("invite");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("brand_owner");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmAttach, setConfirmAttach] = useState(false);
  const filteredAgencies = useMemo(() => agencies.filter((agency) => agency.name.toLowerCase().includes(search.toLowerCase())), [agencies, search]);
  const steps = [t("platform.provision.organization"), t("platform.provision.contact"), t("platform.provision.review")];

  async function submit() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setLoading(true); setError(null);
    try {
      const result = await platformApi.createBrandPlatform({ agency_id: agencyId, name: name.trim(), status, default_language: language, contact_mode: mode, contact_email: mode === "none" ? null : email.trim(), contact_role: role, confirm_existing_user: mode === "attach" }, token);
      onCreated(result);
    } catch (err) { setError(err instanceof ApiError ? err.message : t("platform.provision.required")); }
    finally { setLoading(false); setConfirmAttach(false); }
  }

  function next() {
    const valid = step === 0 ? Boolean(agencyId && name.trim().length >= 2) : step === 1 ? mode === "none" || email.includes("@") : true;
    if (!valid) { setError(t("platform.provision.required")); return; }
    setError(null);
    if (step < 2) setStep(step + 1);
    else if (mode === "attach") setConfirmAttach(true);
    else void submit();
  }

  const agencyName = agencies.find((agency) => agency.id === agencyId)?.name ?? "—";
  const brandRoleOptions = [
    ["brand_owner", t("platform.role.brandOwner")],
    ["brand_manager", t("platform.role.brandManager")],
    ["brand_viewer", t("platform.role.brandViewer")],
    ["external_approver", t("platform.role.externalApprover")],
  ];
  return <>
    <ModalFrame activeStep={step} onClose={onClose} steps={steps} title={t("platform.provision.brandTitle")}>
      {error && <div className="mb-4 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      {step === 0 && <div className="space-y-4">
        <label className="block text-xs font-medium text-text-muted">{t("platform.provision.searchAgency")}<input className={`${fieldClass} mt-1.5`} onChange={(e) => setSearch(e.target.value)} value={search} /></label>
        <label className="block text-xs font-medium text-text-muted">{t("platform.provision.parentAgency")}<select className={`${fieldClass} mt-1.5`} data-testid="brand-agency" onChange={(e) => setAgencyId(e.target.value)} value={agencyId}>{filteredAgencies.map((agency) => <option key={agency.id} value={agency.id}>{agency.name}</option>)}</select></label>
        <label className="block text-xs font-medium text-text-muted">{t("platform.provision.brandName")}<input className={`${fieldClass} mt-1.5`} data-testid="brand-name" onChange={(e) => setName(e.target.value)} value={name} /></label>
        <div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-medium text-text-muted">{t("platform.provision.status")}<select className={`${fieldClass} mt-1.5`} onChange={(e) => setStatus(e.target.value as typeof status)} value={status}><option value="active">{t("platform.provision.active")}</option><option value="suspended">{t("platform.provision.suspended")}</option><option value="archived">{t("platform.provision.archived")}</option></select></label><label className="text-xs font-medium text-text-muted">{t("platform.provision.language")}<select className={`${fieldClass} mt-1.5`} onChange={(e) => setLanguage(e.target.value as typeof language)} value={language}><option value="tr">{t("platform.provision.turkish")}</option><option value="en">{t("platform.provision.english")}</option></select></label></div>
      </div>}
      {step === 1 && <div className="space-y-4"><ModePicker email={email} labels={{ invite: t("platform.provision.inviteContact"), attach: t("platform.provision.attachContact"), none: t("platform.provision.noContact"), email: t("platform.provision.contactEmail") }} onChange={setMode} onEmail={setEmail} value={mode} />{mode !== "none" && <label className="block text-xs font-medium text-text-muted">{t("platform.provision.role")}<select className={`${fieldClass} mt-1.5`} onChange={(e) => setRole(e.target.value)} value={role}>{brandRoleOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}</div>}
      {step === 2 && <dl className="divide-y divide-border rounded-xl border border-border bg-surface-2 px-4"><ReviewRow label={t("platform.provision.parentAgency")} value={agencyName} /><ReviewRow label={t("platform.provision.brandName")} value={name} /><ReviewRow label={t("platform.provision.status")} value={status} /><ReviewRow label={t("platform.provision.summaryContact")} value={mode === "none" ? t("platform.provision.none") : `${mode}: ${email} (${role})`} /></dl>}
      <Footer lastStep={2} loading={loading} onBack={() => setStep(Math.max(0, step - 1))} onCancel={onClose} onNext={next} step={step} />
    </ModalFrame>
    <ConfirmActionModal details={{ action: t("platform.confirm.attach"), agency: agencyName, brand: name, user: email, role }} loading={loading} onClose={() => setConfirmAttach(false)} onConfirm={() => void submit()} open={confirmAttach} />
  </>;
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-start justify-between gap-4 py-3"><dt className="text-xs font-medium text-text-muted">{label}</dt><dd className="max-w-[65%] break-words text-right text-sm font-medium text-text">{value}</dd></div>;
}
