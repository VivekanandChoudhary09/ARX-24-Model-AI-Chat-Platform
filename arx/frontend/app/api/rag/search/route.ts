import { proxyToBackend } from "@/lib/server";

export async function POST(request: Request): Promise<Response> {
  return proxyToBackend("/api/rag/search", { method: "POST", body: await request.text() });
}
