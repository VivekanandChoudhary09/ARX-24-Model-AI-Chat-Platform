"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DocumentAdminTable } from "@/components/admin/DocumentAdminTable";
import { HealthBadge } from "@/components/chat/HealthBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { DocumentRecord, User } from "@/lib/types";

export default function AdminDocumentsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [tags, setTags] = useState("");

  async function load() {
    setDocuments(await api.documents());
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
          <h1 className="text-2xl font-semibold">Document corpus</h1>
          <p className="text-sm text-muted-foreground">Upload, exclude, and delete private RAG documents.</p>
        </div>
        <div className="flex items-center gap-3">
          <HealthBadge />
          <Link href="/" className="text-sm underline">
            Back to chat
          </Link>
        </div>
      </div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Input type="file" onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          await api.uploadDocument(file, tags);
          event.target.value = "";
          await load();
        }} />
        <Input placeholder="tags, comma-separated" value={tags} onChange={(event) => setTags(event.target.value)} />
        <Button variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>
      <DocumentAdminTable documents={documents} onChange={() => void load()} />
    </main>
  );
}
