"use client";

import type { ReactElement } from "react";

import type { ModelRecord } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

function priceLabel(model: ModelRecord): string {
  if (model.input_price_per_1m == null && model.output_price_per_1m == null) {
    return "price n/a";
  }
  const input = model.input_price_per_1m == null ? "—" : `$${model.input_price_per_1m}`;
  const output = model.output_price_per_1m == null ? "—" : `$${model.output_price_per_1m}`;
  return `${input} / ${output} per 1M`;
}

export function ModelPicker({
  models,
  value,
  onChange,
}: {
  models: ModelRecord[];
  value: string;
  onChange: (modelId: string) => void;
}): ReactElement {
  return (
    <div className="flex items-center gap-2">
      <select
        className="h-10 max-w-md rounded-md border border-input bg-background px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {models.map((model) => (
          <option key={model.model_id} value={model.model_id}>
            {model.label} · {model.provider} · {priceLabel(model)}
          </option>
        ))}
      </select>
      {models
        .filter((model) => model.model_id === value)
        .map((model) => (
          <Badge key={model.model_id}>{model.provider}</Badge>
        ))}
    </div>
  );
}
