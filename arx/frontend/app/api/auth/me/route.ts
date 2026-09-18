import { proxyToBackend } from "@/lib/server";

export async function GET(): Promise<Response> {
  return proxyToBackend("/api/auth/me");
}
