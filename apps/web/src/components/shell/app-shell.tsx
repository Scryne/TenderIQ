"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ClipboardCheck,
  CreditCard,
  FileStack,
  Gavel,
  LogOut,
  Menu,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: typeof FileStack;
  soon?: boolean;
};

type NavSection = { label: string | null; items: NavItem[] };

// Kenar çubuğu bölümleri (§7.1): ilk bölüm etiketsiz, diğerleri overline.
const NAV_SECTIONS: NavSection[] = [
  {
    label: null,
    items: [
      { href: "/tenders", label: "İhalelerim", icon: FileStack },
      { href: "/capability", label: "Yetkinlik profili", icon: ClipboardCheck },
    ],
  },
  {
    label: "Hesap",
    items: [
      { href: "/usage", label: "Kullanım ve abonelik", icon: CreditCard },
      { href: "/settings", label: "Ayarlar", icon: Settings },
    ],
  },
];

// Breadcrumb etiketleri — dinamik segmentler (UUID) tür etiketiyle gösterilir.
function breadcrumbFor(pathname: string): { label: string; href?: string }[] {
  if (pathname.startsWith("/tenders")) {
    const parts = pathname.split("/").filter(Boolean);
    const crumbs: { label: string; href?: string }[] = [
      { label: "İhalelerim", href: "/tenders" },
    ];
    if (parts.length >= 2) crumbs.push({ label: "İhale detayı", href: `/tenders/${parts[1]}` });
    if (parts[2] === "review") crumbs.push({ label: "İnceleme" });
    return crumbs;
  }
  if (pathname.startsWith("/capability")) return [{ label: "Yetkinlik profili" }];
  if (pathname.startsWith("/usage")) return [{ label: "Kullanım ve abonelik" }];
  if (pathname.startsWith("/settings")) return [{ label: "Ayarlar" }];
  return [];
}

function initialsOf(name: string | null | undefined, email: string | undefined): string {
  const source = name?.trim() !== "" && name != null ? name : (email ?? "?");
  return source
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function SidebarNav({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3">
      {NAV_SECTIONS.map((section) => (
        <div key={section.label ?? "main"} className="flex flex-col gap-1">
          {section.label !== null && (
            <div className="text-overline mt-4 px-3 pb-1 text-ink-3">{section.label}</div>
          )}
          {section.items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            if (item.soon) {
              return (
                <span
                  key={item.href}
                  aria-disabled
                  className="flex h-9 cursor-default items-center gap-2.5 rounded-md px-3 text-sm font-medium text-ink-3"
                >
                  <item.icon className="size-[18px]" strokeWidth={1.5} />
                  {item.label}
                  <Badge variant="outline" className="ml-auto text-[10px] text-ink-3">
                    Yakında
                  </Badge>
                </span>
              );
            }
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex h-9 items-center gap-2.5 rounded-md px-3 text-sm font-medium transition-colors",
                  active
                    ? "rail-active bg-brand-weak text-brand"
                    : "text-ink-2 hover:bg-surface-2 hover:text-ink-1",
                )}
              >
                <item.icon className="size-[18px]" strokeWidth={1.5} />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function UserFooter() {
  const router = useRouter();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/me");
      if (error !== undefined) throw new Error("Oturum bilgisi alınamadı.");
      return data;
    },
  });

  const memberships = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/memberships");
      if (error !== undefined) throw new Error("Organizasyonlar alınamadı.");
      return data;
    },
  });

  async function logout() {
    await fetch("/api/session", { method: "DELETE" });
    router.push("/login");
    router.refresh();
  }

  async function switchOrg(organizationId: string) {
    const response = await fetch("/api/session/switch-org", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ organization_id: organizationId }),
    });
    if (response.ok) router.refresh();
  }

  const orgs = memberships.data ?? [];

  const name = me.data?.full_name ?? me.data?.email ?? "…";

  return (
    <div className="border-t px-3 py-3">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-surface-2"
          >
            <Avatar className="size-8">
              <AvatarFallback className="bg-brand-weak text-xs font-semibold text-brand">
                {initialsOf(me.data?.full_name, me.data?.email)}
              </AvatarFallback>
            </Avatar>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-semibold text-ink-1">{name}</span>
              <span className="block truncate text-xs text-ink-3">
                {me.data?.role === "admin"
                  ? "Yönetici"
                  : me.data?.role === "member"
                    ? "Üye"
                    : me.data?.role === "viewer"
                      ? "İzleyici"
                      : ""}
              </span>
            </span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          <DropdownMenuLabel className="truncate">{me.data?.email}</DropdownMenuLabel>
          {orgs.length > 1 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-overline text-ink-3">
                Organizasyon
              </DropdownMenuLabel>
              {orgs.map((org) => (
                <DropdownMenuItem
                  key={org.organization_id}
                  disabled={org.is_active}
                  onSelect={() => void switchOrg(org.organization_id)}
                >
                  <Check
                    className={cn("size-4", org.is_active ? "text-brand" : "opacity-0")}
                    strokeWidth={2}
                  />
                  <span className="truncate">{org.organization_name}</span>
                </DropdownMenuItem>
              ))}
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => void logout()}>
            <LogOut className="size-4" strokeWidth={1.5} />
            Oturumu kapat
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function SidebarBody({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-6 py-5">
        <span className="flex size-8 items-center justify-center rounded-lg bg-brand text-primary-foreground">
          <Gavel className="size-4.5" strokeWidth={1.75} />
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-ink-1">TenderIQ</span>
      </div>
      <SidebarNav pathname={pathname} onNavigate={onNavigate} />
      <UserFooter />
    </div>
  );
}

/**
 * Uygulama kabuğu (DESIGN §6.5): 256px sabit kenar çubuğu + 56px üst çubuk.
 * 1024px altında kenar çubuğu Sheet çekmecesine düşer (§12 responsive taban).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const crumbs = breadcrumbFor(pathname);

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-surface lg:block">
        <SidebarBody pathname={pathname} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-canvas/95 px-4 backdrop-blur-sm lg:px-8">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Menüyü aç">
                <Menu className="size-5" strokeWidth={1.5} />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <SheetTitle className="sr-only">Gezinme</SheetTitle>
              <SidebarBody pathname={pathname} onNavigate={() => setDrawerOpen(false)} />
            </SheetContent>
          </Sheet>

          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
            {crumbs.map((crumb, index) => {
              const last = index === crumbs.length - 1;
              return (
                <span key={crumb.label} className="flex items-center gap-1.5">
                  {index > 0 && <span className="text-ink-3">›</span>}
                  {crumb.href !== undefined && !last ? (
                    <Link href={crumb.href} className="text-ink-3 transition-colors hover:text-ink-1">
                      {crumb.label}
                    </Link>
                  ) : (
                    <span className={last ? "font-medium text-ink-1" : "text-ink-3"}>
                      {crumb.label}
                    </span>
                  )}
                </span>
              );
            })}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-[1520px] flex-1 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
