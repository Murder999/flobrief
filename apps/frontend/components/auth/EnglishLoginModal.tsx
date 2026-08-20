"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { AlertCircle, ArrowLeft, Building2, Mail, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { authApi, ApiError } from "@/lib/api-client";

type View = "roles" | "login" | "forgot" | "sent";

export function EnglishLoginModal({ open, onClose, returnTo }: { open: boolean; onClose: () => void; returnTo?: string }) {
  const { login, isLoading } = useAuth();
  const panelRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>("roles");
  const [role, setRole] = useState<"agency" | "brand">("agency");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setView("roles");
    setError(null);
    const onKeyDown = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => panelRef.current?.focus());
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, open]);

  if (!open) return null;

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await login({ email, password }, returnTo);
      onClose();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) setError("The email address or password is incorrect.");
      else if (caught instanceof ApiError && caught.status === 429) setError("Too many attempts. Wait a few minutes and try again.");
      else setError("We couldn’t log you in. Please try again.");
    }
  }

  async function submitReset(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await authApi.forgotPassword(email);
      setView("sent");
    } catch {
      setView("sent");
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onMouseDown={onClose}>
      <div className="absolute inset-0 bg-background/80 backdrop-blur-md" />
      <div ref={panelRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="english-login-title" onMouseDown={(event) => event.stopPropagation()} className="relative w-full max-w-sm rounded-2xl border border-border bg-surface shadow-modal outline-none">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <span className="text-sm font-bold text-text">PostPiloter</span>
          <button type="button" onClick={onClose} aria-label="Close" className="flex h-10 w-10 items-center justify-center rounded-xl text-text-muted hover:bg-hover hover:text-text"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-6">
          {view === "roles" && (
            <>
              <h2 id="english-login-title" className="text-lg font-bold text-text">Choose your workspace</h2>
              <p className="mt-1 text-sm text-text-muted">Select how you use PostPiloter.</p>
              <div className="mt-5 grid gap-3">
                {([{ value: "agency", icon: Building2, title: "Agency workspace", description: "Manage clients, briefs, production, and your team." }, { value: "brand", icon: Sparkles, title: "Brand portal", description: "Review briefs, deliverables, feedback, and approvals." }] as const).map(({ value, icon: Icon, title, description }) => (
                  <button key={value} type="button" onClick={() => { setRole(value); setView("login"); }} className="flex min-h-20 items-center gap-4 rounded-xl border border-border bg-background p-4 text-left transition-colors hover:border-accent/40 hover:bg-accent-subtle/40">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-subtle text-accent"><Icon className="h-5 w-5" /></span>
                    <span><strong className="block text-sm text-text">{title}</strong><span className="mt-1 block text-xs leading-5 text-text-muted">{description}</span></span>
                  </button>
                ))}
              </div>
            </>
          )}
          {view === "login" && (
            <form onSubmit={submitLogin}>
              <button type="button" onClick={() => setView("roles")} className="mb-4 inline-flex items-center gap-1 text-xs text-text-muted hover:text-accent"><ArrowLeft className="h-3.5 w-3.5" />Back</button>
              <h2 id="english-login-title" className="text-lg font-bold text-text">Log in to your {role === "agency" ? "agency workspace" : "brand portal"}</h2>
              <div className="mt-5 space-y-4">
                <label className="block text-xs font-medium text-text-muted">Email address<input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-text outline-none focus:border-accent" /></label>
                <label className="block text-xs font-medium text-text-muted">Password<input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-text outline-none focus:border-accent" /></label>
              </div>
              <button type="button" onClick={() => setView("forgot")} className="mt-3 text-xs text-accent">Forgot password?</button>
              {error && <p role="alert" className="mt-4 flex gap-2 rounded-xl border border-danger/20 bg-danger/10 p-3 text-sm text-danger"><AlertCircle className="h-4 w-4 flex-none" />{error}</p>}
              <Button type="submit" isLoading={isLoading} className="mt-5 w-full">Log in</Button>
            </form>
          )}
          {view === "forgot" && (
            <form onSubmit={submitReset}>
              <button type="button" onClick={() => setView("login")} className="mb-4 inline-flex items-center gap-1 text-xs text-text-muted"><ArrowLeft className="h-3.5 w-3.5" />Back</button>
              <h2 id="english-login-title" className="text-lg font-bold text-text">Reset your password</h2>
              <p className="mt-1 text-sm text-text-muted">We’ll send a reset link if an account exists for this address.</p>
              <label className="mt-5 block text-xs font-medium text-text-muted">Email address<input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-text outline-none focus:border-accent" /></label>
              <Button type="submit" className="mt-5 w-full">Send reset link</Button>
            </form>
          )}
          {view === "sent" && <div className="text-center"><Mail className="mx-auto h-10 w-10 text-success" /><h2 id="english-login-title" className="mt-4 text-lg font-bold text-text">Check your email</h2><p className="mt-2 text-sm leading-6 text-text-muted">If an account exists for <strong className="text-text">{email}</strong>, a reset link is on its way.</p><Button type="button" variant="secondary" className="mt-5 w-full" onClick={() => setView("login")}>Back to login</Button></div>}
        </div>
      </div>
    </div>
  );
}
