"use client";

import type { SourceChunk } from "@/lib/types";
import { ScrollArea } from "@/components/ui/scroll-area";

export function SourcePanel({ sources }: { sources: SourceChunk[] }): React.ReactElement | null {
  if (!sources.length) return null;
  return (
    <details className="border-t border-border bg-card/70 px-4 py-2" open>
      <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
        Sources ({sources.length})
      </summary>
      <ScrollArea className="mt-2 max-h-40">
        <div className="space-y-2">
          {sources.map((source, index) => (
            <div key={`${source.document_id}-${source.chunk_index}-${index}`} className="rounded-md border border-border p-2">
              <p className="text-xs font-medium">
                {source.filename}
                {source.heading ? ` · ${source.heading}` : ""}
              </p>
              <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">{source.text}</p>
            </div>
          ))}
        </div>
      </ScrollArea>
    </details>
  );
}
