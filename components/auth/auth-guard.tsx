"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api/client";

export function AuthGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    apiFetch("/v1/auth/me")
      .then(() => { if (active) setReady(true); })
      .catch(() => { if (active) router.replace("/login"); });
    return () => { active = false; };
  }, [pathname, router]);

  if (!ready) {
    return <main className="grid min-h-screen place-items-center text-sm text-muted-foreground">Checking your secure session�</main>;
  }
  return children;
}
