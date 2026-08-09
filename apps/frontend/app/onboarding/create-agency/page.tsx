"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { agencyApi } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { getPendingPlan, clearPendingPlan } from "@/lib/workspace";

export default function CreateAgencyPage() {
  const router = useRouter();
  const { accessToken } = useAuth();
  const { refreshWorkspaces, switchAgency } = useWorkspace();
  const [name, setName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !accessToken) return;

    setIsLoading(true);
    setError(null);

    try {
      const agency = await agencyApi.create({ name: name.trim() }, accessToken);
      await refreshWorkspaces();
      switchAgency(agency.id);
      const pendingPlan = getPendingPlan();
      if (pendingPlan) {
        clearPendingPlan();
        router.replace(`/dashboard/settings/billing?upgrade=${pendingPlan.planId}&yearly=${pendingPlan.yearly}`);
      } else {
        router.replace("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Agency oluşturulamadı");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-accent/20 rounded-2xl mb-4">
            <span className="text-xl font-bold text-accent">F</span>
          </div>
          <h1 className="text-2xl font-bold text-text">Ajansınızı Oluşturun</h1>
          <p className="mt-2 text-sm text-text-muted">
            Başlamak için ajansınıza bir isim verin
          </p>
        </div>

        <div className="bg-surface border border-border rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <Input
              label="Ajans Adı"
              placeholder="Örnek Ajans"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />

            {error && (
              <div className="px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg">
                <p className="text-sm text-danger">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={isLoading || !name.trim()}
            >
              {isLoading ? "Oluşturuluyor…" : "Ajansı Oluştur"}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-text-muted">
          Daha sonra ajans ayarlarından logonuzu ve diğer bilgilerinizi ekleyebilirsiniz.
        </p>
      </div>
    </div>
  );
}
