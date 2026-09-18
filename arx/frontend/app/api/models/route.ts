import { proxyToBackend } from "@/lib/server";

export async function GET(): Promise<Response> {
  return proxyToBackend("/api/models");
}

export async function POST(request: Request): Promise<Response> {
  return proxyToBackend("/api/models", { method: "POST", body: await request.text() });
}
