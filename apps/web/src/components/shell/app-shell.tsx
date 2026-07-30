"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Check,
  ChevronsUpDown,
  ClipboardCheck,
  CreditCard,
  FileStack,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════════════════════
 * UYGULAMA KABUĞU — DESIGN.md §7.1-7.2 · §8.9
 *
 * Sidebar 264px (daraltılmış 64px) · üst çubuk 56px · içerik maks 1440px.
 * Çok kiracılı üründe kenar çubuğunun en üstünde çalışma alanı seçici bulunur
 * (§8.9) — kullanıcı hangi organizasyonda olduğunu her an görmelidir.
 *
 * Aktif nav öğesi: `surface-2` zemin + `ink-1` metin + 500 ağırlık.
 * Sol aksan çubuğu KULLANILMAZ — §7.2 ikisini birden yasaklar, ayrıca 2px
 * şerit bu üründe kanıt bağının imzasıdır (bkz. components/evidence.tsx) ve
 * navigasyonda kullanılırsa anlamı ucuzlar.
 * ═══════════════════════════════════════════════════════════════════════════ */

type NavItem = { href: string; label: string; icon: LucideIcon };
type NavSection = { label: string | null; items: NavItem[] };

const NAV_SECTIONS: NavSection[] = [
  {
    label: null,
    items: [
      { href: "/panel", label: "Panel", icon: LayoutDashboard },
      { href: "/tenders", label: "İhalelerim", icon: FileStack },
    ],
  },
  {
    label: "ANALİZ",
    items: [{ href: "/capability", label: "Yetkinlik profili", icon: ClipboardCheck }],
  },
  {
    label: "HESAP",
    items: [
      { href: "/usage", label: "Kullanım ve abonelik", icon: CreditCard },
      { href: "/settings", label: "Ayarlar", icon: Settings },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Yönetici",
  member: "Üye",
  viewer: "İzleyici",
};

export type ShellUser = {
  name: string;
  email: string;
  role: string;
};

export type ShellOrg = {
  id: string;
  name: string;
  planName?: string | null;
  isActive: boolean;
};

/* ───────────────────────────── Breadcrumb ───────────────────────────────── */

type Crumb = { label: string; href?: string };

export function breadcrumbFor(pathname: string): Crumb[] {
  if (pathname.startsWith("/tenders")) {
    const parts = pathname.split("/").filter(Boolean);
    const crumbs: Crumb[] = [{ label: "İhalelerim", href: "/tenders" }];
    if (parts.length >= 2) {
      crumbs.push({ label: "İhale detayı", href: `/tenders/${parts[1]}` });
    }
    if (parts[2] === "review") crumbs.push({ label: "İnceleme" });
    return crumbs;
  }
  if (pathname.startsWith("/panel")) return [{ label: "Panel" }];
  if (pathname.startsWith("/capability")) return [{ label: "Yetkinlik profili" }];
  if (pathname.startsWith("/usage")) return [{ label: "Kullanım ve abonelik" }];
  if (pathname.startsWith("/settings")) return [{ label: "Ayarlar" }];
  return [];
}

function initialsOf(name: string, email: string): string {
  const source = name.trim() !== "" ? name : email;
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase("tr-TR") ?? "")
    .join("");
}

/* ────────────────────── Çalışma alanı seçici (§8.9) ─────────────────────── */

function WorkspaceSwitcher({
  orgs,
  collapsed,
  onSwitch,
}: {
  orgs: ShellOrg[];
  collapsed: boolean;
  onSwitch: (id: string) => void;
}) {
  const active = orgs.find((org) => org.isActive) ?? orgs[0];

  const mark = (
    <span className="grid size-8 shrink-0 place-items-center rounded-md bg-accent text-ink-on-accent">
      {/* Marka işareti: iki paralel çizgi + nokta — "kaynağa bağlı satır".
          Ürünün imza motifinin en küçük hali. */}
      <svg viewBox="0 0 20 20" className="size-4" aria-hidden fill="none">
        <path d="M3 4.5h14M3 10h10M3 15.5h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="16.5" cy="15.5" r="1.75" fill="currentColor" />
      </svg>
    </span>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Link href="/panel" className="mx-auto block w-fit p-2" aria-label="TenderIQ — panele git">
            {mark}
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">{active?.name ?? "TenderIQ"}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-12 w-full items-center gap-2.5 rounded-md px-2 text-left transition-colors duration-[120ms] hover:bg-surface-2"
        >
          {mark}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-ink-1">
              {active?.name ?? "TenderIQ"}
            </span>
            <span className="block truncate text-xs text-ink-3">
              {active?.planName ?? "TenderIQ"}
            </span>
          </span>
          {/* Çift ok = "değiştirilebilir" sinyali; tek chevron değil (§8.9). */}
          <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-ink-3" strokeWidth={1.75} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-overline text-ink-3">
          ÇALIŞMA ALANLARI
        </DropdownMenuLabel>
        {orgs.map((org) => (
          <DropdownMenuItem
            key={org.id}
            disabled={org.isActive}
            onSelect={() => onSwitch(org.id)}
            className="gap-2"
          >
            <Check
              aria-hidden
              className={cn("size-4", org.isActive ? "text-ink-1" : "opacity-0")}
              strokeWidth={2.5}
            />
            <span className="min-w-0 flex-1 truncate">{org.name}</span>
            {org.planName != null && (
              <span className="shrink-0 text-xs text-ink-3">{org.planName}</span>
            )}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <Building2 strokeWidth={1.75} />
            Çalışma alanı ayarları
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/* ──────────────────────────── Gezinme (§7.2) ────────────────────────────── */

function SidebarNav({
  pathname,
  collapsed,
  onNavigate,
}: {
  pathname: string;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-1">
      {NAV_SECTIONS.map((section) => (
        <div key={section.label ?? "main"} className="flex flex-col gap-0.5">
          {section.label !== null && !collapsed && (
            <div className="text-overline px-2.5 pb-1.5 text-ink-3">{section.label}</div>
          )}
          {section.label !== null && collapsed && (
            <div aria-hidden className="mx-2 mb-1.5 h-px bg-border" />
          )}
          {section.items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const link = (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 items-center gap-2.5 rounded-md text-sm transition-colors duration-[120ms] ease-out",
                  collapsed ? "justify-center px-0" : "px-2.5",
                  active
                    ? "bg-nav-active font-medium text-ink-1"
                    : "font-normal text-ink-2 hover:bg-hover",
                )}
              >
                <item.icon aria-hidden className="size-4 shrink-0" strokeWidth={1.75} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );

            return collapsed ? (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
        </div>
      ))}
    </nav>
  );
}

/* ────────────────────────── Kullanıcı kartı ─────────────────────────────── */

function UserCard({
  user,
  collapsed,
  onLogout,
}: {
  user: ShellUser | null;
  collapsed: boolean;
  onLogout: () => void;
}) {
  const initials = user === null ? "" : initialsOf(user.name, user.email);

  return (
    <div className={cn("border-t border-border p-3", collapsed && "px-2")}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            disabled={user === null}
            // `aria-label` YOK (bilinçli). Buton görünür metin taşıyor
            // (kullanıcı adı + rol); sabit bir `aria-label` erişilebilir adı
            // "Hesap menüsü"ne indirir ve görünen metni ADIN DIŞINDA bırakır.
            // Bu WCAG 2.5.3 "Label in Name" ihlalidir: sesli komutla "Berkay"
            // diyen kullanıcı butonu çalıştıramaz (Lighthouse
            // `label-content-name-mismatch` — 2026-07-30'da tüm kimlikli
            // sayfalarda ölçüldü). Amaç bilgisi aşağıdaki gizli metinle
            // veriliyor, böylece ad görünen metni KAPSAR.
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md py-1.5 text-left transition-colors duration-[120ms] hover:bg-surface-2 disabled:opacity-60",
              collapsed ? "justify-center px-0" : "px-2",
            )}
          >
            <Avatar className="size-8">
              <AvatarFallback className="text-xs font-semibold">
                {initials === "" ? "—" : initials}
              </AvatarFallback>
            </Avatar>
            {!collapsed && (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink-1">
                  {user?.name ?? "…"}
                </span>
                <span className="block truncate text-xs text-ink-3">
                  {user === null ? "" : (ROLE_LABELS[user.role] ?? user.role)}
                </span>
              </span>
            )}
            {/* Daraltılmışken görünen tek şey baş harfler; butonun ne yaptığı
                yalnız ekran okuyucuya bu metinle söylenir. Görünür metin adın
                İÇİNDE kaldığı için 2.5.3 korunur. */}
            <span className="sr-only">hesap menüsü</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top" className="w-60">
          <DropdownMenuLabel className="truncate font-normal text-ink-3">
            {user?.email}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link href="/settings">
              <Settings strokeWidth={1.75} />
              Hesap ayarları
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onLogout}>
            <LogOut strokeWidth={1.75} />
            Oturumu kapat
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

/* ──────────────────────── Sunum kabuğu (veri yok) ───────────────────────── */

export function ShellFrame({
  pathname,
  user,
  orgs,
  onSwitchOrg,
  onLogout,
  children,
}: {
  pathname: string;
  user: ShellUser | null;
  orgs: ShellOrg[];
  onSwitchOrg: (id: string) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const crumbs = breadcrumbFor(pathname);

  // Daraltma tercihi oturumlar arasında korunur; ilk boyada localStorage
  // okunamayacağı için efektte uygulanır (hydration uyumsuzluğu olmasın).
  useEffect(() => {
    setCollapsed(window.localStorage.getItem("tiq.sidebar") === "collapsed");
  }, []);

  function toggleCollapsed() {
    setCollapsed((previous) => {
      const next = !previous;
      window.localStorage.setItem("tiq.sidebar", next ? "collapsed" : "expanded");
      return next;
    });
  }

  const sidebarBody = (mobile: boolean) => {
    const isCollapsed = mobile ? false : collapsed;
    return (
      <div className="flex h-full flex-col">
        <div className={cn("flex items-center gap-1 p-3", isCollapsed && "flex-col px-2")}>
          <div className="min-w-0 flex-1">
            <WorkspaceSwitcher
              orgs={orgs}
              collapsed={isCollapsed}
              onSwitch={onSwitchOrg}
            />
          </div>
          {!mobile && (
            <Button
              variant="ghost"
              size="icon-sm"
              className="shrink-0"
              aria-label={isCollapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
              onClick={toggleCollapsed}
            >
              {isCollapsed ? (
                <PanelLeftOpen strokeWidth={1.75} />
              ) : (
                <PanelLeftClose strokeWidth={1.75} />
              )}
            </Button>
          )}
        </div>
        <SidebarNav
          pathname={pathname}
          collapsed={isCollapsed}
          onNavigate={mobile ? () => setDrawerOpen(false) : undefined}
        />
        <UserCard user={user} collapsed={isCollapsed} onLogout={onLogout} />
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-canvas">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-border bg-surface transition-[width] duration-200 ease-out lg:block",
          collapsed ? "w-16" : "w-[264px]",
        )}
      >
        {sidebarBody(false)}
      </aside>

      <div
        className={cn(
          "flex min-w-0 flex-col transition-[padding] duration-200 ease-out",
          collapsed ? "lg:pl-16" : "lg:pl-[264px]",
        )}
      >
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-canvas/90 px-4 backdrop-blur-sm lg:px-8">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="lg:hidden" aria-label="Menüyü aç">
                <Menu strokeWidth={1.75} />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[264px] p-0">
              <SheetTitle className="sr-only">Gezinme</SheetTitle>
              {sidebarBody(true)}
            </SheetContent>
          </Sheet>

          {/* §9.1 — breadcrumb yalnız 2+ seviye derinlikte anlamlı; tek
              seviyede sayfa başlığını tekrarlamaktan başka iş yapmaz. */}
          <nav aria-label="Konum" className="flex min-w-0 flex-1 items-center gap-1.5 text-sm">
            {(crumbs.length > 1 ? crumbs : []).map((crumb, index) => {
              const last = index === crumbs.length - 1;
              return (
                <span key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
                  {index > 0 && (
                    <span aria-hidden className="text-border-strong">
                      /
                    </span>
                  )}
                  {crumb.href !== undefined && !last ? (
                    <Link
                      href={crumb.href}
                      className="truncate text-ink-3 transition-colors duration-[120ms] hover:text-ink-1"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span
                      aria-current={last ? "page" : undefined}
                      className={cn("truncate", last ? "font-medium text-ink-1" : "text-ink-3")}
                    >
                      {crumb.label}
                    </span>
                  )}
                </span>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" asChild aria-label="İhalelerde ara">
                  <Link href="/tenders">
                    <Search strokeWidth={1.75} />
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>İhalelerde ara</TooltipContent>
            </Tooltip>
            <ThemeToggle />
          </div>
        </header>

        {/* İçerik 1440px'de sabitlenir ve geniş ekranda ortalanır (§7.4). */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

/* ──────────────────────── Veri bağlı kabuk ──────────────────────────────── */

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
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

  const user: ShellUser | null =
    me.data === undefined
      ? null
      : {
          name: me.data.full_name ?? me.data.email,
          email: me.data.email,
          role: me.data.role,
        };

  const orgs: ShellOrg[] = (memberships.data ?? []).map((org) => ({
    id: org.organization_id,
    name: org.organization_name,
    isActive: org.is_active,
  }));

  return (
    <ShellFrame
      pathname={pathname}
      user={user}
      orgs={orgs}
      onSwitchOrg={(id) => void switchOrg(id)}
      onLogout={() => void logout()}
    >
      {children}
    </ShellFrame>
  );
}
