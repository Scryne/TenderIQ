"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";

const ROLES = [
  { value: "admin", label: "Yönetici" },
  { value: "member", label: "Üye" },
  { value: "viewer", label: "İzleyici" },
] as const;

type Role = (typeof ROLES)[number]["value"];

const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ROLES.map((r) => [r.value, r.label]),
);

type Member = {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  email_verified: boolean;
};

export function MembersSection({ isAdmin, currentUserId }: { isAdmin: boolean; currentUserId?: string }) {
  const queryClient = useQueryClient();
  const [removing, setRemoving] = useState<Member | null>(null);

  const members = useQuery({
    queryKey: ["members"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/members");
      if (error !== undefined) throw new Error("Üyeler alınamadı.");
      return data;
    },
  });

  const changeRole = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: Role }) => {
      const { error } = await api.PATCH("/api/v1/members/{user_id}", {
        params: { path: { user_id: userId } },
        body: { role },
      });
      if (error !== undefined) {
        const message = (error as { error?: { message?: string } })?.error?.message;
        throw new Error(message ?? "Rol değiştirilemedi (son yönetici düşürülemez).");
      }
    },
    onSuccess: () => {
      toast.success("Rol güncellendi.");
      void queryClient.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: async (userId: string) => {
      const { error } = await api.DELETE("/api/v1/members/{user_id}", {
        params: { path: { user_id: userId } },
      });
      if (error !== undefined) {
        const message = (error as { error?: { message?: string } })?.error?.message;
        throw new Error(message ?? "Üye çıkarılamadı (son yönetici çıkarılamaz).");
      }
    },
    onSuccess: () => {
      toast.success("Üye çıkarıldı.");
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      setRemoving(null);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Üyeler</CardTitle>
      </CardHeader>
      <CardContent>
        {members.isPending && <Skeleton className="h-24 w-full" />}
        {members.isError && <p className="text-sm text-danger">{members.error.message}</p>}
        {members.data && (
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow className="bg-surface-2/60 hover:bg-surface-2/60">
                  <TableHead className="text-xs font-medium text-ink-2">Üye</TableHead>
                  <TableHead className="w-40 text-xs font-medium text-ink-2">Rol</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.data.map((member: Member) => {
                  const isSelf = member.user_id === currentUserId;
                  return (
                    <TableRow key={member.user_id} className="h-14">
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="flex items-center gap-2 font-medium text-ink-1">
                            {member.full_name ?? member.email}
                            {!member.email_verified && (
                              <StatusPill tone="neutral" label="Doğrulanmadı" />
                            )}
                          </span>
                          {member.full_name && (
                            <span className="text-xs text-ink-3">{member.email}</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {isAdmin && !isSelf ? (
                          <Select
                            value={member.role}
                            onValueChange={(role) =>
                              changeRole.mutate({ userId: member.user_id, role: role as Role })
                            }
                          >
                            <SelectTrigger className="h-8 w-36">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {ROLES.map((role) => (
                                <SelectItem key={role.value} value={role.value}>
                                  {role.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <span className="text-sm text-ink-2">
                            {ROLE_LABEL[member.role] ?? member.role}
                            {isSelf && <span className="text-ink-3"> (siz)</span>}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isAdmin && !isSelf && (
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Üyeyi çıkar"
                            onClick={() => setRemoving(member)}
                          >
                            <Trash2 className="size-4 text-ink-3" strokeWidth={1.5} />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      <Dialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Üyeyi çıkar</DialogTitle>
            <DialogDescription>
              {removing?.full_name ?? removing?.email} organizasyondan çıkarılacak ve oturumları
              sonlandırılacak. Bu işlem geri alınamaz.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoving(null)}>
              Vazgeç
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => removing && remove.mutate(removing.user_id)}
            >
              {remove.isPending ? "Çıkarılıyor…" : "Çıkar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
