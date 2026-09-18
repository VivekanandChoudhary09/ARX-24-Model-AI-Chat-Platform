"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ModelAdminTable } from "@/components/admin/ModelAdminTable";
import { HealthBadge } from "@/components/chat/HealthBadge";
import { api } from "@/lib/api";
import type { ModelRecord, User } from "@/lib/types";

export default function AdminModelsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [models, setModels] = useState<ModelRecord[]>([]);

  async function load() {
    const payload = await api.modelsAll();
    setModels(payload.models);
  }

  useEffect(() => {
    api
      .me()
      .then(async (current) => {
        if (current.role !== "admin") {
          router.push("/");
          return;
        }
        setUser(current);
        await load();
      })
      .catch(() => router.push("/login"));
  }, [router]);

  if (!user) return null;

  return (
    <main className="min-h-screen p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Model registry</h1>
          <p className="text-sm text-muted-foreground">Enable, reorder, or add models with zero restart.</p>
        </div>
        <div className="flex items-center gap-3">
          <HealthBadge />
          <Link href="/" className="text-sm underline">
            Back to chat
          </Link>
        </div>
      </div>
      <ModelAdminTable models={models} onChange={() => void load()} />
    </main>
  );
}
