"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function Composer({
  disabled,
  streaming,
  onSend,
  onStop,
}: {
  disabled?: boolean;
  streaming: boolean;
  onSend: (message: string) => void;
  onStop: () => void;
}): React.ReactElement {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-border bg-card p-4">
      <div className="mx-auto flex max-w-4xl gap-3">
        <Textarea
          value={value}
          disabled={disabled}
          placeholder="Message ARX… Enter to send, Shift+Enter for a newline"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="min-h-[72px] resize-none"
        />
        {streaming ? (
          <Button variant="destructive" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <Button onClick={submit} disabled={disabled || !value.trim()}>
            Send
          </Button>
        )}
      </div>
    </div>
  );
}
