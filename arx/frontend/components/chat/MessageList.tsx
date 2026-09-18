"use client";

import { MessageBubble } from "./MessageBubble";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage } from "@/lib/types";

export function MessageList({
  messages,
  streamingId,
}: {
  messages: ChatMessage[];
  streamingId?: string | null;
}): React.ReactElement {
  return (
    <ScrollArea className="h-full px-6 py-4">
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        {messages.length === 0 && (
          <p className="pt-16 text-center text-sm text-muted-foreground">
            Start a conversation. ARX will stream tokens from the selected model.
          </p>
        )}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            streaming={streamingId === message.id}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
