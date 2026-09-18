import { cookies } from "next/headers";

const COOKIE = "arx_access_token";

export function backendUrl(path: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base}${path}`;
}

export async function proxyHeaders(extra?: HeadersInit): Promise<Headers> {
  const store = await cookies();
  const token = store.get(COOKIE)?.value;
  const headers = new Headers(extra);
  headers.set("X-Internal-Key", process.env.INTERNAL_API_KEY || "");
  headers.set("Origin", "http://localhost:3000");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

export async function setAuthCookie(token: string): Promise<void> {
  const store = await cookies();
  store.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: false,
    maxAge: 60 * 60,
  });
}

export async function clearAuthCookie(): Promise<void> {
  const store = await cookies();
  store.delete(COOKIE);
}

export async function proxyToBackend(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = await proxyHeaders(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(backendUrl(path), {
    ...init,
    headers,
    cache: "no-store",
  });
  const contentType = response.headers.get("Content-Type") || "application/json";
  if (contentType.includes("text/event-stream") && response.body) {
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }
  const text = await response.text();
  return new Response(text, {
    status: response.status,
    headers: { "Content-Type": contentType },
  });
}

export async function proxyAuth(path: string, request: Request): Promise<Response> {
  const body = await request.text();
  const response = await fetch(backendUrl(path), {
    method: "POST",
    headers: await proxyHeaders({ "Content-Type": "application/json" }),
    body,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (response.ok && data?.access_token) {
    await setAuthCookie(data.access_token);
    return Response.json({ user: data.user });
  }
  return Response.json(data, { status: response.status });
}
