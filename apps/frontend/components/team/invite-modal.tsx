"use client";

import { useState } from "react";
import { invitationApi } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";

const AGENCY_ROLE_OPTIONS = [
  { value: "admin", label: "Yönetici" },
  { value: "brand_manager", label: "Marka Yöneticisi" },
  { value: "designer", label: "Tasarımcı" },
  { value: "developer", label: "Geliştirici" },
  { value: "social_media_manager", label: "Sosyal Medya" },
  { value: "viewer", label: "Görüntüleyici" },
];

interface InviteModalProps {
  isOpen: boolean;
  onClose: () => void;
  agencyId: string;
  accessToken: string;
  onSuccess: () => void;
}

export function InviteModal({
  isOpen,
  onClose,
  agencyId,
  accessToken,
  onSuccess,
}: InviteModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("admin");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      await invitationApi.inviteAgencyMember(
        agencyId,
        { email: email.trim().toLowerCase(), role, message: message.trim() || undefined },
        accessToken
      );
      setEmail("");
      setRole("admin");
      setMessage("");
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Davet gönderilemedi");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Ekip Üyesi Davet Et">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="E-posta Adresi"
          type="email"
          placeholder="merhaba@sirket.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Select
          label="Rol"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          options={AGENCY_ROLE_OPTIONS}
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
            Mesaj (İsteğe bağlı)
          </label>
          <textarea
            className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg text-sm
              text-text placeholder:text-text-muted focus:outline-none focus:border-accent
              focus:ring-2 focus:ring-accent/20 transition-all resize-none"
            rows={3}
            placeholder="Davet mesajınız..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={500}
          />
        </div>

        {error && (
          <div className="px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg">
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            İptal
          </Button>
          <Button type="submit" disabled={isLoading || !email.trim()}>
            {isLoading ? "Gönderiliyor…" : "Davet Gönder"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
