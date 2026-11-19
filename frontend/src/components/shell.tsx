"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import {
  Bell, BookOpen, ClipboardList, CreditCard, FileText, Gauge, Globe2, LayoutDashboard, LogOut, Menu, PenLine,
  ScrollText, Settings, Shield, ShieldCheck, Users, X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";
import { cx, Spinner } from "./ui";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="VisaReady AI home">
      <span className={cx("flex h-8 w-8 items-center justify-center rounded-lg", light ? "bg-white/10" : "bg-navy")}>
        <ShieldCheck className="h-4.5 w-4.5 text-white" aria-hidden />
      </span>
      <span className={cx("text-[15px] font-semibold tracking-tight", light ? "text-white" : "text-ink")}>
        VisaReady <span className="text-accent">AI</span>
      </span>
    </Link>
  );
}

export function SiteHeader() {
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const links = [["/#how", "How it works"], ["/#evidence", "Evidence Intelligence"], ["/#pricing", "Pricing"], ["/knowledge", "Knowledge Centre"]];
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Logo />
        <nav className="hidden items-center gap-6 md:flex" aria-label="Main">
          {links.map(([h, l]) => <Link key={h} href={h} className="text-sm text-ink-2 hover:text-ink">{l}</Link>)}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {me ? (
            <Link href={me.is_staff ? "/admin" : "/dashboard"} className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-2">Open dashboard</Link>
          ) : (
            <>
              <Link href="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-ink-2 hover:text-ink">Sign in</Link>
              <Link href="/register" className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-2">Get started</Link>
            </>
          )}
        </div>
        <button className="md:hidden" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}>{open ? <X /> : <Menu />}</button>
      </div>
      {open && (
        <div className="border-t border-line bg-surface px-4 py-3 md:hidden">
          {links.map(([h, l]) => <Link key={h} href={h} onClick={() => setOpen(false)} className="block py-2 text-sm text-ink-2">{l}</Link>)}
          <Link href={me ? "/dashboard" : "/register"} className="mt-2 block rounded-lg bg-navy px-4 py-2 text-center text-sm font-medium text-white">{me ? "Open dashboard" : "Get started"}</Link>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid grid-cols-1 max-w-6xl gap-8 px-4 py-10 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo />
          <p className="mt-3 max-w-md text-sm text-ink-3">
            VisaReady AI is an independent application-preparation tool. We are not affiliated with any government or immigration
            authority, we do not provide legal advice, and we cannot guarantee any visa outcome.
          </p>
        </div>
        <div className="text-sm">
          <p className="font-medium text-ink">Product</p>
          <ul className="mt-2 space-y-1.5 text-ink-3">
            <li><Link href="/#pricing" className="hover:text-ink">Pricing</Link></li>
            <li><Link href="/services" className="hover:text-ink">Document writing</Link></li>
            <li><Link href="/knowledge" className="hover:text-ink">Knowledge Centre</Link></li>
          </ul>
        </div>
        <div className="text-sm">
          <p className="font-medium text-ink">Legal</p>
          <ul className="mt-2 space-y-1.5 text-ink-3">
            <li><Link href="/legal/terms" className="hover:text-ink">Terms of Service</Link></li>
            <li><Link href="/legal/privacy" className="hover:text-ink">Privacy Policy</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line py-4 text-center text-xs text-ink-3">© VisaReady AI · Independent visa preparation platform</div>
    </footer>
  );
}

const appNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/applications", label: "Applications", icon: ClipboardList },
  { href: "/profile", label: "My profile", icon: FileText },
  { href: "/services", label: "Writing services", icon: PenLine },
  { href: "/orders", label: "My orders", icon: ScrollText },
  { href: "/knowledge", label: "Knowledge Centre", icon: BookOpen },
  { href: "/payments", label: "Payments", icon: CreditCard },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/settings", label: "Privacy & security", icon: Settings },
];

const adminNav = [
  { href: "/admin", label: "Overview", icon: Gauge, perm: "admin.access" },
  { href: "/admin/orders", label: "Writing orders", icon: PenLine, perm: "writing_orders.read" },
  { href: "/admin/knowledge", label: "Knowledge base", icon: Globe2, perm: "knowledge.read" },
  { href: "/admin/users", label: "Users", icon: Users, perm: "users.read" },
  { href: "/admin/payments", label: "Payments & refunds", icon: CreditCard, perm: "payments.read" },
  { href: "/admin/privacy", label: "Privacy & retention", icon: Shield, perm: "privacy.manage" },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText, perm: "audit.read" },
];

type NavItem = { href: string; label: string; icon: typeof Gauge };
type SidebarProps = { items: NavItem[]; footer?: ReactNode; onNavigate?: () => void };

// usePathname() is request data: it must sit inside <Suspense> (Cache Components). The fallback
// renders the same navigation without the active highlight.
function Sidebar(props: SidebarProps) {
  return <Suspense fallback={<SidebarView {...props} path="" />}><SidebarWithPath {...props} /></Suspense>;
}

function SidebarWithPath(props: SidebarProps) {
  return <SidebarView {...props} path={usePathname()} />;
}

function SidebarView({ items, footer, onNavigate, path }: SidebarProps & { path: string }) {
  return (
    <nav className="flex h-full flex-col gap-1 p-3" aria-label="App">
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === "/admin" || href === "/dashboard" ? path === href : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={onNavigate}
            className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
              active ? "bg-white/10 font-medium text-white" : "text-white/70 hover:bg-white/5 hover:text-white")}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        );
      })}
      <div className="mt-auto">{footer}</div>
    </nav>
  );
}

function Frame({ nav, children, ready }: { nav: { href: string; label: string; icon: typeof Gauge }[]; children: ReactNode; ready: boolean }) {
  const { me, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    if (ready) api<{ unread: number }>("/notifications").then((n) => setUnread(n.unread)).catch(() => {});
  }, [ready]);
  const footer = (
    <div className="space-y-2 border-t border-white/10 pt-3">
      <p className="truncate px-3 text-xs text-white/60">{me?.email}</p>
      <button onClick={async () => { await logout(); router.push("/"); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-white/70 hover:bg-white/5 hover:text-white">
        <LogOut className="h-4 w-4" aria-hidden /> Sign out
      </button>
    </div>
  );
  return (
    <div className="min-h-dvh lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-navy lg:flex">
        <div className="flex h-16 items-center px-5"><Logo light /></div>
        <Sidebar items={nav} footer={footer} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal>
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-navy">
            <div className="flex h-16 items-center justify-between px-5"><Logo light /><button onClick={() => setOpen(false)} aria-label="Close menu"><X className="text-white" /></button></div>
            <Sidebar items={nav} footer={footer} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-surface/90 px-4 backdrop-blur lg:px-8">
        <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button>
        <p className="hidden text-sm text-ink-3 lg:block">Welcome back{me ? `, ${me.full_name.split(" ")[0]}` : ""}</p>
        <Link href="/notifications" className="relative rounded-lg p-2 text-ink-2 hover:bg-surface-2" aria-label={`Notifications (${unread} unread)`}>
          <Bell className="h-5 w-5" />
          {unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-bad" />}
        </Link>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 lg:px-8 lg:py-8">{ready ? <Suspense fallback={<Spinner />}>{children}</Suspense> : <Spinner />}</main>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { ready } = useRequireAuth();
  return <Frame nav={appNav} ready={ready}>{children}</Frame>;
}

export function AdminShell({ children, permission = "admin.access" }: { children: ReactNode; permission?: string }) {
  const { ready, me } = useRequireAuth(permission);
  const nav = adminNav.filter((n) => me?.permissions.includes(n.perm));
  return <Frame nav={nav} ready={ready}>{children}</Frame>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-ink-3">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
