import { proxyToBackend } from "@/lib/server";

type Params = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  return proxyToBackend(`/api/conversations/${id}`);
}

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  return proxyToBackend(`/api/conversations/${id}`, { method: "PATCH", body: await request.text() });
}

export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  return proxyToBackend(`/api/conversations/${id}`, { method: "DELETE" });
}
