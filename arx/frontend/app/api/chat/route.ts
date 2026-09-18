import { proxyToBackend } from "@/lib/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return proxyToBackend("/api/chat", {
    method: "POST",
    body,
    headers: { "Content-Type": "application/json" },
  });
}
