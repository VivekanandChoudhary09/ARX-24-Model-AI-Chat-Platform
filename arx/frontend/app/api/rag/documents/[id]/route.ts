import { proxyToBackend } from "@/lib/server";

type Params = { params: Promise<{ id: string }> };

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  return proxyToBackend(`/api/rag/documents/${id}`, { method: "PATCH", body: await request.text() });
}

export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  return proxyToBackend(`/api/rag/documents/${id}`, { method: "DELETE" });
}
