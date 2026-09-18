import { clearAuthCookie, proxyToBackend } from "@/lib/server";

export async function POST(): Promise<Response> {
  const response = await proxyToBackend("/api/auth/logout", { method: "POST" });
  await clearAuthCookie();
  return response;
}
