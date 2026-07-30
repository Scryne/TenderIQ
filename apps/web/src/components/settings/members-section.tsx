"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, InlineError } from "@/components/states";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogBody,
  DialogClose,
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
import { formatNumber } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/tenders";

const ROLES = [
  { value: "admin", label: "Yönetici" },
  { value: "member", label: "Üye" },
  { value: "viewer", label: "İzleyici" },
] as const;

type Role = (typeof ROLES)[number]["value"];

type Member = {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  email_verified: boolean;
};

function initialsOf(member: Member): string {
  const source = member.full_name?.trim() !== "" && member.full_name != null ? member.full_name : member.email;
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase("tr-TR") ?? "")
    .join("");
}

export function MembersSection({
  isAdmin,
  currentUserId,
}: {
  isAdmin: boolean;
  currentUserId?: string;
}) {
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
        throw new Error(message ?? "Rol değiştirilemedi. Son yönetici düşürülemez.");
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
        throw new Error(message ?? "Üye çıkarılamadı. Son yönetici çıkarılamaz.");
      }
    },
    onSuccess: () => {
      toast.success("Üye çıkarıldı.");
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      setRemoving(null);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const rows = (members.data ?? []) as Member[];

  return (
    <>
      <Card>
        <CardHeader>
          <div className="min-w-0">
            <CardTitle as="h2">Üyeler</CardTitle>
            <CardDescription>
              {isAdmin
                ? "Rol değişikliği anında geçerli olur. Son yönetici düşürülemez ya da çıkarılamaz."
                : "Üye ekleme ve rol değiştirme yönetici yetkisi gerektirir."}
            </CardDescription>
          </div>
          {rows.length > 0 && <Badge tone="neutral">{formatNumber(rows.length)} üye</Badge>}
        </CardHeader>
        <CardContent className="pt-0">
          {members.isPending && <Skeleton className="h-32 w-full" />}
          {members.isError && (
            <InlineError message={members.error.message} onRetry={() => void members.refetch()} />
          )}
          {members.data !== undefined && rows.length === 0 && (
            <EmptyState
              icon={Users}
              title="Yalnız sizsiniz"
              description="Davetler sekmesinden ekip arkadaşlarınızı çağırın; incelemeleri birlikte yürütün."
              compact
            />
          )}
          {rows.length > 0 && (
            <div className="overflow-hidden rounded-sm border border-border">
              {/* §7.4 — mobilde tablo kart listesine döner; üç sütun 375px'de
                  sıkışıp rol seçicisini kullanılamaz hale getiriyordu. */}
              <ul className="divide-y divide-border md:hidden">
                {rows.map((member) => {
                  const isSelf = member.user_id === currentUserId;
                  return (
                    <li key={member.user_id} className="flex flex-col gap-3 p-4">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <Avatar className="size-8 shrink-0">
                          <AvatarFallback className="text-xs font-semibold">
                            {initialsOf(member)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink-1">
                            {member.full_name ?? member.email}
                          </p>
                          {member.full_name != null && (
                            <p className="truncate text-xs text-ink-3">{member.email}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {isAdmin && !isSelf ? (
                          <Select
                            value={member.role}
                            onValueChange={(role) =>
                              changeRole.mutate({ userId: member.user_id, role: role as Role })
                            }
                          >
                            <SelectTrigger size="sm" className="w-36" aria-label="Üye rolü">
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
                          <Badge tone="neutral">
                            {ROLE_LABELS[member.role] ?? member.role}
                            {isSelf && " (siz)"}
                          </Badge>
                        )}
                        {!member.email_verified && <Badge tone="warning">Doğrulanmadı</Badge>}
                        {isAdmin && !isSelf && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="ml-auto text-ink-3 hover:bg-danger-weak hover:text-danger"
                            aria-label={`${member.full_name ?? member.email} üyesini çıkar`}
                            onClick={() => setRemoving(member)}
                          >
                            <Trash2 strokeWidth={1.75} />
                          </Button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>

              <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow className="border-b-0 hover:bg-transparent">
                    <TableHead>ÜYE</TableHead>
                    <TableHead className="w-44">ROL</TableHead>
                    <TableHead className="w-14 text-right">{isAdmin ? "İŞLEM" : ""}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((member) => {
                    const isSelf = member.user_id === currentUserId;
                    return (
                      <TableRow key={member.user_id}>
                        <TableCell className="max-w-0">
                          <div className="flex min-w-0 items-center gap-2.5">
                            <Avatar className="size-8 shrink-0">
                              <AvatarFallback className="text-xs font-semibold">
                                {initialsOf(member)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <span className="flex min-w-0 items-center gap-2">
                                <span className="truncate font-medium text-ink-1">
                                  {member.full_name ?? member.email}
                                </span>
                                {!member.email_verified && (
                                  <Badge tone="warning">Doğrulanmadı</Badge>
                                )}
                              </span>
                              {member.full_name != null && (
                                <span className="block truncate text-xs text-ink-3">
                                  {member.email}
                                </span>
                              )}
                            </div>
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
                              <SelectTrigger size="sm" className="w-36" aria-label="Üye rolü">
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
                              {ROLE_LABELS[member.role] ?? member.role}
                              {isSelf && <span className="text-ink-3"> (siz)</span>}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {isAdmin && !isSelf && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              className="text-ink-3 hover:bg-danger-weak hover:text-danger"
                              aria-label={`${member.full_name ?? member.email} üyesini çıkar`}
                              onClick={() => setRemoving(member)}
                            >
                              <Trash2 strokeWidth={1.75} />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* §8.7 — yıkıcı işlemde onay butonu eylemi TEKRAR EDER, "Sil" demez. */}
      <Dialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle>Üyeyi çıkar</DialogTitle>
            <DialogDescription>
              <span className="font-medium text-ink-1">
                {removing?.full_name ?? removing?.email}
              </span>{" "}
              bu çalışma alanından çıkarılacak ve açık oturumları sonlandırılacak. İnceleme
              geçmişindeki kayıtları korunur.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <p className="text-sm text-ink-2">Bu işlem geri alınamaz.</p>
          </DialogBody>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="secondary">İptal</Button>
            </DialogClose>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() => removing !== null && remove.mutate(removing.user_id)}
            >
              Üyeyi çıkar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
