"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { StatusPill, type StatusTone } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

const ROLES = [
  { value: "member", label: "Üye" },
  { value: "viewer", label: "İzleyici" },
  { value: "admin", label: "Yönetici" },
] as const;

type InviteRole = (typeof ROLES)[number]["value"];

const ROLE_LABEL: Record<string, string> = {
  admin: "Yönetici",
  member: "Üye",
  viewer: "İzleyici",
};

type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  expired: boolean;
};

function statusPill(inv: Invitation): { tone: StatusTone; label: string } {
  if (inv.expired) return { tone: "neutral", label: "Süresi doldu" };
  return { tone: "info", label: "Bekliyor" };
}

export function InvitationsSection() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<InviteRole>("member");

  const invitations = useQuery({
    queryKey: ["invitations"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/invitations");
      if (error !== undefined) throw new Error("Davetler alınamadı.");
      return data;
    },
  });

  const invite = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/invitations", {
        body: { email, role },
      });
      if (error !== undefined) {
        const message = (error as { error?: { message?: string } })?.error?.message;
        throw new Error(message ?? "Davet gönderilemedi.");
      }
    },
    onSuccess: () => {
      toast.success("Davet gönderildi.");
      setEmail("");
      void queryClient.invalidateQueries({ queryKey: ["invitations"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const revoke = useMutation({
    mutationFn: async (invitationId: string) => {
      const { error } = await api.DELETE("/api/v1/invitations/{invitation_id}", {
        params: { path: { invitation_id: invitationId } },
      });
      if (error !== undefined) throw new Error("Davet iptal edilemedi.");
    },
    onSuccess: () => {
      toast.success("Davet iptal edildi.");
      void queryClient.invalidateQueries({ queryKey: ["invitations"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Davetler</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            invite.mutate();
          }}
        >
          <div className="min-w-[220px] flex-1 space-y-1.5">
            <Label htmlFor="invite-email">E-posta</Label>
            <Input
              id="invite-email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="uye@firma.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="invite-role">Rol</Label>
            <Select value={role} onValueChange={(value) => setRole(value as InviteRole)}>
              <SelectTrigger id="invite-role" className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={invite.isPending}>
            <Send className="size-4" strokeWidth={1.5} />
            {invite.isPending ? "Gönderiliyor…" : "Davet et"}
          </Button>
        </form>

        {invitations.isPending && <Skeleton className="h-12 w-full" />}
        {invitations.isError && (
          <p className="text-sm text-danger">{invitations.error.message}</p>
        )}
        {invitations.data && invitations.data.length === 0 && (
          <p className="text-sm text-ink-3">Bekleyen davet yok.</p>
        )}
        {invitations.data && invitations.data.length > 0 && (
          <div className="divide-y rounded-lg border">
            {invitations.data.map((inv: Invitation) => {
              const pill = statusPill(inv);
              return (
                <div key={inv.id} className="flex items-center gap-3 px-4 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-1">{inv.email}</p>
                    <p className="text-xs text-ink-3">{ROLE_LABEL[inv.role] ?? inv.role}</p>
                  </div>
                  <StatusPill tone={pill.tone} label={pill.label} />
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Daveti iptal et"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(inv.id)}
                  >
                    <X className="size-4 text-ink-3" strokeWidth={1.5} />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
