import { proxyAuth } from "@/lib/server";

export async function POST(request: Request): Promise<Response> {
  return proxyAuth("/api/auth/register", request);
}
