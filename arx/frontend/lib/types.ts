export type Role = "user" | "admin";

export type User = {
  id: string;
  email: string;
  role: Role;
  plan: string;
  monthly_token_quota: number;
  created_at: string;
  last_login_at: string | null;
  is_active: boolean;
};

export type ModelRecord = {
  model_id: string;
  label: string;
  provider: string;
  channel: "primary" | "secondary";
  fallback_model_id: string | null;
  enabled: boolean;
  order: number;
  context_window: number;
  supports_streaming: boolean;
  supports_vision: boolean;
  input_price_per_1m: number | null;
  output_price_per_1m: number | null;
};

export type SourceChunk = {
  document_id: string;
  filename: string;
  chunk_index: number;
  heading: string | null;
  text: string;
  tags: string[];
};

export type ConversationSummary = {
  id: string;
  title: string;
  model_id: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  archived: boolean;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model_id?: string | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  latency_ms?: number | null;
  first_token_ms?: number | null;
  sources?: SourceChunk[];
  created_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
};

export type DocumentRecord = {
  id: string;
  user_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  chunk_count: number;
  status: "pending" | "processing" | "ready" | "failed";
  excluded: boolean;
  tags: string[];
  created_at: string;
  error?: string | null;
};

export type SseMeta = {
  type: "meta";
  conversation_id: string;
  model_id: string;
  sources: SourceChunk[];
};

export type SseToken = { type: "token"; content: string };
export type SseDone = {
  type: "done";
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  first_token_ms: number | null;
  cost_usd: number;
};
export type SseError = { type: "error"; code: string; message: string };
export type SseFrame = SseMeta | SseToken | SseDone | SseError;

export type QuotaError = {
  code: "quota_exceeded";
  message: string;
  limit: number;
  used: number;
  resets_at: string;
};

export type HealthStatus = { mongo: boolean };
