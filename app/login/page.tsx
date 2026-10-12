"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { ApiError, apiFetch } from "@/lib/api/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!email.trim() || !/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await apiFetch("/v1/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      router.replace("/dashboard");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to sign in. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-background px-4 py-12">
      <div className="pointer-events-none absolute -top-36 right-0 size-[440px] rounded-full bg-primary/5 blur-3xl" />
      <section className="relative w-full max-w-md rounded-2xl border border-border/70 bg-card p-7 shadow-xl sm:p-9">
        <div className="mb-8 flex items-center gap-3">
          <Image src="/sagefold-mark.svg" alt="" width={44} height={44} priority />
          <div><p className="text-lg font-semibold">Sagefold</p><p className="text-sm text-muted-foreground">Your private knowledge workspace</p></div>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in or create your account</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">Use your email and password. The first sign in creates your account automatically.</p>
        <form onSubmit={submit} className="mt-7 space-y-5">
          <label className="block space-y-2 text-sm font-medium">Email
            <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 w-full rounded-lg border border-input bg-background px-3 font-normal outline-none focus:ring-2 focus:ring-primary/40" placeholder="you@example.com" />
          </label>
          <label className="block space-y-2 text-sm font-medium">Password
            <span className="relative block">
              <input type={showPassword ? "text" : "password"} autoComplete="current-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 w-full rounded-lg border border-input bg-background px-3 pr-11 font-normal outline-none focus:ring-2 focus:ring-primary/40" placeholder="At least 8 characters" />
              <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
            </span>
          </label>
          {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <button disabled={loading} className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-60">
            <LockKeyhole className="size-4" />{loading ? "Signing in�" : "Continue securely"}
          </button>
        </form>
        <p className="mt-6 rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">Forgotten passwords cannot be recovered or reset. Keep your password safe; there is no recovery process.</p>
      </section>
    </main>
  );
}
