import type {
  ConversationDetail,
  ConversationSummary,
  DocumentRecord,
  HealthStatus,
  ModelRecord,
  User,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const error = new Error(data?.message || `Request failed (${response.status})`);
    (error as Error & { payload?: unknown; status?: number }).payload = data;
    (error as Error & { payload?: unknown; status?: number }).status = response.status;
    throw error;
  }
  return data as T;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  me: () => request<User>("/api/auth/me"),
  register: (email: string, password: string) =>
    request<{ user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  models: () => request<{ models: ModelRecord[] }>("/api/models"),
  modelsAll: () => request<{ models: ModelRecord[] }>("/api/models/all"),
  createModel: (payload: Partial<ModelRecord> & { model_id: string; label: string; provider: string }) =>
    request<ModelRecord>("/api/models", { method: "POST", body: JSON.stringify(payload) }),
  patchModel: (modelId: string, payload: Partial<ModelRecord>) =>
    request<ModelRecord>(`/api/models/${encodeURIComponent(modelId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteModel: (modelId: string) =>
    request<{ ok: boolean }>(`/api/models/${encodeURIComponent(modelId)}`, { method: "DELETE" }),
  conversations: () => request<ConversationSummary[]>("/api/conversations"),
  conversation: (id: string) => request<ConversationDetail>(`/api/conversations/${id}`),
  renameConversation: (id: string, title: string) =>
    request<ConversationSummary>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (id: string) =>
    request<{ ok: boolean }>(`/api/conversations/${id}`, { method: "DELETE" }),
  documents: () => request<DocumentRecord[]>("/api/rag/documents"),
  uploadDocument: async (file: File, tags = "") => {
    const body = new FormData();
    body.append("file", file);
    body.append("tags", tags);
    const response = await fetch("/api/rag/documents", { method: "POST", body, credentials: "include" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.message || "Upload failed");
    }
    return data as DocumentRecord;
  },
  patchDocument: (id: string, payload: { excluded?: boolean }) =>
    request<DocumentRecord>(`/api/rag/documents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteDocument: (id: string) =>
    request<{ ok: boolean }>(`/api/rag/documents/${id}`, { method: "DELETE" }),
  ragSearch: (query: string) =>
    request<{ layer: string; chunks: SourceChunkLike[] }>("/api/rag/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
};

type SourceChunkLike = {
  document_id: string;
  filename: string;
  chunk_index: number;
  heading: string | null;
  text: string;
};
