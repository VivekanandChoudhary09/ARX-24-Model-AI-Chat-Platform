"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { HealthBadge } from "@/components/chat/HealthBadge";
import { MessageList } from "@/components/chat/MessageList";
import { ModelPicker } from "@/components/chat/ModelPicker";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/api";
import { readSse } from "@/lib/sse";
import type { ChatMessage, ConversationSummary, ModelRecord, QuotaError, SourceChunk, User } from "@/lib/types";

const DEV = process.env.NODE_ENV === "development";

export default function ChatPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [modelId, setModelId] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [firstTokenMs, setFirstTokenMs] = useState<number | null>(null);
  const [quotaError, setQuotaError] = useState<QuotaError | null>(null);
  const [useRag, setUseRag] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!user) return;
    void refreshSidebar();
    api.models().then((payload) => {
      setModels(payload.models);
      if (payload.models[0]) setModelId(payload.models[0].model_id);
    });
  }, [user]);

  async function refreshSidebar() {
    const items = await api.conversations();
    setConversations(items);
  }

  async function openConversation(id: string) {
    const detail = await api.conversation(id);
    setConversationId(detail.id);
    setMessages(detail.messages);
    setSources(detail.messages.find((item) => item.role === "assistant")?.sources || []);
    if (detail.model_id) setModelId(detail.model_id);
  }

  async function send(text: string) {
    setQuotaError(null);
    setFirstTokenMs(null);
    const userMessage: ChatMessage = {
      id: `local-user-${Date.now()}`,
      conversation_id: conversationId || "new",
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    const assistantId = `local-assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      conversation_id: conversationId || "new",
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      sources: [],
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setStreaming(true);
    setStreamingId(assistantId);
    const controller = new AbortController();
    abortRef.current = controller;
    const started = performance.now();
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        credentials: "include",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: text,
          model_id: modelId,
          use_rag: useRag,
        }),
      });
      if (response.status === 429) {
        const payload = (await response.json()) as QuotaError;
        setQuotaError(payload);
        setStreaming(false);
        setStreamingId(null);
        return;
      }
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ message: "Chat failed" }));
        throw new Error(payload.message || "Chat failed");
      }
      await readSse(
        response,
        (frame) => {
          if (frame.type === "meta") {
            setConversationId(frame.conversation_id);
            setSources(frame.sources);
            setModelId(frame.model_id);
          } else if (frame.type === "token") {
            if (firstTokenMs == null) {
              setFirstTokenMs(Math.round(performance.now() - started));
            }
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId ? { ...item, content: item.content + frame.content } : item,
              ),
            );
          } else if (frame.type === "done") {
            setFirstTokenMs(frame.first_token_ms);
            void refreshSidebar();
          } else if (frame.type === "error") {
            if (frame.code === "quota_exceeded") {
              setQuotaError({
                code: "quota_exceeded",
                message: frame.message,
                limit: 0,
                used: 0,
                resets_at: "",
              });
            } else {
              setMessages((current) =>
                current.map((item) =>
                  item.id === assistantId
                    ? { ...item, content: item.content || `Error: ${frame.message}` }
                    : item,
                ),
              );
            }
          }
        },
        controller.signal,
      );
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId
              ? { ...item, content: item.content || `Error: ${(error as Error).message}` }
              : item,
          ),
        );
      }
    } finally {
      setStreaming(false);
      setStreamingId(null);
      abortRef.current = null;
    }
  }

  const selected = useMemo(
    () => models.find((model) => model.model_id === modelId),
    [models, modelId],
  );

  return (
    <div className="flex h-screen">
      <aside className="flex w-72 flex-col border-r border-border bg-card">
        <div className="flex items-center justify-between px-4 py-4">
          <div>
            <p className="text-lg font-semibold tracking-tight">ARX</p>
            <p className="text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <HealthBadge />
        </div>
        <div className="px-3">
          <Button
            className="w-full"
            variant="secondary"
            onClick={() => {
              setConversationId(null);
              setMessages([]);
              setSources([]);
            }}
          >
            New chat
          </Button>
        </div>
        <ScrollArea className="mt-3 flex-1 px-2">
          {conversations.map((item) => (
            <button
              key={item.id}
              onClick={() => void openConversation(item.id)}
              className={`mb-1 w-full rounded-md px-3 py-2 text-left text-sm hover:bg-accent ${
                conversationId === item.id ? "bg-accent" : ""
              }`}
            >
              <span className="line-clamp-1">{item.title}</span>
            </button>
          ))}
        </ScrollArea>
        <div className="space-y-2 border-t border-border p-3 text-sm">
          {user?.role === "admin" && (
            <>
              <Link className="block text-muted-foreground hover:text-foreground" href="/admin/models">
                Admin · models
              </Link>
              <Link className="block text-muted-foreground hover:text-foreground" href="/admin/documents">
                Admin · documents
              </Link>
            </>
          )}
          <button
            className="text-muted-foreground hover:text-foreground"
            onClick={async () => {
              await api.logout();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <ModelPicker models={models} value={modelId} onChange={setModelId} />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={useRag} onChange={(event) => setUseRag(event.target.checked)} />
            Use RAG
          </label>
          {DEV && firstTokenMs != null && (
            <span className="text-xs text-muted-foreground">first token {firstTokenMs} ms</span>
          )}
          {selected?.fallback_model_id && (
            <span className="text-xs text-muted-foreground">fallback {selected.fallback_model_id}</span>
          )}
        </header>
        <div className="min-h-0 flex-1">
          <MessageList messages={messages} streamingId={streamingId} />
        </div>
        {quotaError && (
          <div className="mx-4 mb-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
            Quota exceeded. limit={quotaError.limit} used={quotaError.used} resets_at={quotaError.resets_at}. Switching
            models will not bypass this budget.
          </div>
        )}
        <SourcePanel sources={sources} />
        <Composer disabled={!modelId || !user} streaming={streaming} onSend={(text) => void send(text)} onStop={() => abortRef.current?.abort()} />
      </section>
    </div>
  );
}
