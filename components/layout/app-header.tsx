"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { LayoutDashboard, FileStack, MessageSquare, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api/client";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Documents", href: "/documents", icon: FileStack },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function AppHeader({ activePath }: { activePath: string }) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try { await apiFetch("/v1/auth/logout", { method: "POST" }); }
    finally { router.replace("/login"); }
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <Image src="/sagefold-mark.svg" alt="" width={36} height={36} priority />
          <span className="text-lg font-semibold tracking-tight">Sagefold</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => {
            const isActive = activePath === item.href || (item.href !== "/dashboard" && activePath.startsWith(item.href));
            return <Link key={item.label} href={item.href} className={cn("flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors", isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}><item.icon className="size-4" />{item.label}</Link>;
          })}
        </nav>
        <button onClick={logout} disabled={loggingOut} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60" aria-label="Log out"><LogOut className="size-4" /><span className="hidden sm:inline">{loggingOut ? "Logging out�" : "Log out"}</span></button>
      </div>
    </header>
  );
}
