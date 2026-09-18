"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { HealthBadge } from "@/components/chat/HealthBadge";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await api.login(email, password);
      } else {
        await api.register(email, password);
      }
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-4 rounded-xl border border-border bg-card p-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">ARX</h1>
          <HealthBadge />
        </div>
        <p className="text-sm text-muted-foreground">
          {mode === "login" ? "Sign in to continue." : "Create the first account to become admin."}
        </p>
        <Input type="email" required placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <Input
          type="password"
          required
          minLength={8}
          placeholder="Password (8+ characters)"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy}>
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
        <button
          type="button"
          className="text-sm text-muted-foreground underline"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
        <p className="text-xs text-muted-foreground">
          Auth tokens stay in an httpOnly cookie. The browser never stores INTERNAL_API_KEY.
        </p>
        <Link href="/" className="block text-xs text-muted-foreground underline">
          Back to chat
        </Link>
      </form>
    </main>
  );
}
