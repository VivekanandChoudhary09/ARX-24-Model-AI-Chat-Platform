"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { ModelRecord } from "@/lib/types";

export function ModelAdminTable({
  models,
  onChange,
}: {
  models: ModelRecord[];
  onChange: () => void;
}): React.ReactElement {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({
    model_id: "",
    label: "",
    provider: "",
    fallback_model_id: "",
  });
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  async function toggle(model: ModelRecord, enabled: boolean) {
    await api.patchModel(model.model_id, { enabled });
    onChange();
  }

  async function reorder(from: number, to: number) {
    if (from === to) return;
    const copy = [...models];
    const [moved] = copy.splice(from, 1);
    copy.splice(to, 0, moved);
    await Promise.all(copy.map((model, index) => api.patchModel(model.model_id, { order: (index + 1) * 10 })));
    onChange();
  }

  async function create() {
    await api.createModel({
      model_id: draft.model_id,
      label: draft.label,
      provider: draft.provider,
      fallback_model_id: draft.fallback_model_id || null,
      enabled: true,
      order: (models.length + 1) * 10,
      context_window: 128000,
      supports_streaming: true,
      supports_vision: false,
    });
    setOpen(false);
    setDraft({ model_id: "", label: "", provider: "", fallback_model_id: "" });
    onChange();
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>Add model</Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead></TableHead>
            <TableHead>Label</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Model ID</TableHead>
            <TableHead>Enabled</TableHead>
            <TableHead>Price in/out</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model, index) => (
            <TableRow
              key={model.model_id}
              draggable
              onDragStart={() => setDragIndex(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => {
                if (dragIndex != null) void reorder(dragIndex, index);
                setDragIndex(null);
              }}
            >
              <TableCell className="cursor-grab text-muted-foreground">↕</TableCell>
              <TableCell>{model.label}</TableCell>
              <TableCell>{model.provider}</TableCell>
              <TableCell className="font-mono text-xs">{model.model_id}</TableCell>
              <TableCell>
                <Switch checked={model.enabled} onCheckedChange={(value) => void toggle(model, value)} />
              </TableCell>
              <TableCell>
                {model.input_price_per_1m ?? "null"} / {model.output_price_per_1m ?? "null"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Dialog open={open} onOpenChange={setOpen} title="Add model">
        <div className="space-y-3">
          <Input
            placeholder="LiteLLM model id (openrouter/openai/gpt-4o)"
            value={draft.model_id}
            onChange={(event) => setDraft({ ...draft, model_id: event.target.value })}
          />
          <Input
            placeholder="Label"
            value={draft.label}
            onChange={(event) => setDraft({ ...draft, label: event.target.value })}
          />
          <Input
            placeholder="Provider"
            value={draft.provider}
            onChange={(event) => setDraft({ ...draft, provider: event.target.value })}
          />
          <Input
            placeholder="Fallback model id (optional)"
            value={draft.fallback_model_id}
            onChange={(event) => setDraft({ ...draft, fallback_model_id: event.target.value })}
          />
          <Button onClick={() => void create()} disabled={!draft.model_id || !draft.label || !draft.provider}>
            Save
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
