"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailPlus, Send, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, InlineError } from "@/components/states";
import { StatusPill, type StatusTone } from "@/components/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { formatDateTime, formatRelative } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/tenders";

const ROLES = [
  { value: "member", label: "Üye" },
  { value: "viewer", label: "İzleyici" },
  { value: "admin", label: "Yönetici" },
] as const;

type InviteRole = (typeof ROLES)[number]["value"];

type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  expired: boolean;
};

function inviteStatus(invitation: Invitation): { tone: StatusTone; label: string } {
  if (invitation.expired) return { tone: "neutral", label: "Süresi doldu" };
  return { tone: "warning", label: "Bekliyor" };
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
      const { error } = await api.POST("/api/v1/invitations", { body: { email, role } });
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

  const rows = (invitations.data ?? []) as Invitation[];

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="block">
          <CardTitle>Yeni davet</CardTitle>
          <CardDescription>
            Davet edilen kişi e-postadaki bağlantıyla hesabını kendisi kurar. Bağlantı 7 gün
            geçerlidir.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              invite.mutate();
            }}
          >
            <div className="flex min-w-[220px] flex-1 flex-col gap-1.5">
              <Label htmlFor="invite-email">
                E-posta <span className="text-danger">*</span>
              </Label>
              <Input
                id="invite-email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="ad.soyad@firma.com.tr"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="invite-role">Rol</Label>
              <Select value={role} onValueChange={(value) => setRole(value as InviteRole)}>
                <SelectTrigger id="invite-role" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" loading={invite.isPending}>
              <Send strokeWidth={1.75} />
              Davet et
            </Button>
          </form>
          <p className="mt-2.5 text-xs text-ink-3">
            İzleyici bulguları görür ama onaylayamaz · Üye inceleme yapar · Yönetici plan ve üye
            yönetir.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="block">
          <CardTitle>Bekleyen davetler</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {invitations.isPending && <Skeleton className="h-16 w-full" />}
          {invitations.isError && (
            <InlineError
              message={invitations.error.message}
              onRetry={() => void invitations.refetch()}
            />
          )}
          {invitations.data !== undefined && rows.length === 0 && (
            <EmptyState
              icon={MailPlus}
              title="Bekleyen davet yok"
              description="Yukarıdaki formla ekip arkadaşınızı çağırın; kabul edilene kadar davet burada görünür."
              compact
            />
          )}
          {rows.length > 0 && (
            <ul className="divide-y divide-border overflow-hidden rounded-sm border border-border">
              {rows.map((invitation) => {
                const status = inviteStatus(invitation);
                return (
                  <li key={invitation.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-1">{invitation.email}</p>
                      <p
                        className="mt-0.5 text-xs text-ink-3"
                        title={formatDateTime(invitation.expires_at)}
                      >
                        Geçerlilik {formatRelative(invitation.expires_at)}
                      </p>
                    </div>
                    <Badge tone="neutral">{ROLE_LABELS[invitation.role] ?? invitation.role}</Badge>
                    <StatusPill tone={status.tone} label={status.label} />
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-ink-3 hover:bg-danger-weak hover:text-danger"
                      aria-label={`${invitation.email} davetini iptal et`}
                      disabled={revoke.isPending}
                      onClick={() => revoke.mutate(invitation.id)}
                    >
                      <X strokeWidth={1.75} />
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
