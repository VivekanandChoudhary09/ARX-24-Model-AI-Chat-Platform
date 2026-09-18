import { proxyToBackend } from "@/lib/server";

export async function GET(): Promise<Response> {
  return proxyToBackend("/api/rag/documents");
}

export async function POST(request: Request): Promise<Response> {
  const form = await request.formData();
  return proxyToBackend("/api/rag/documents", { method: "POST", body: form });
}
