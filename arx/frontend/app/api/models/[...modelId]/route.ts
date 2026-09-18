import { proxyToBackend } from "@/lib/server";

type Params = { params: Promise<{ modelId: string[] }> };

function joinModelId(parts: string[]): string {
  return parts.map((part) => decodeURIComponent(part)).join("/");
}

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { modelId } = await params;
  const id = joinModelId(modelId);
  return proxyToBackend(`/api/models/${id}`, { method: "PATCH", body: await request.text() });
}

export async function DELETE(_request: Request, { params }: Params): Promise<Response> {
  const { modelId } = await params;
  const id = joinModelId(modelId);
  return proxyToBackend(`/api/models/${id}`, { method: "DELETE" });
}
