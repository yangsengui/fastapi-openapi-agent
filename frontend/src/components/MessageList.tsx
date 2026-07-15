import { ChevronDown, ChevronRight } from "lucide-react";
import type { RefObject } from "react";

import { ui } from "../app/styles";
import type { Message, MessagePart, Role, ToolResult } from "../types";
import { renderMarkdown } from "../lib/markdown";
import { cn, safeJson } from "../lib/utils";

type MessageListProps = {
  messages: Message[];
  scrollRef: RefObject<HTMLDivElement | null>;
};

export function MessageList({ messages, scrollRef }: MessageListProps) {
  return (
    <section ref={scrollRef} className={ui.messages}>
      {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
    </section>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.parts?.length) {
    return (
      <article className={messageClass(message.role)}>
        {message.parts.map((part) => {
          if (part.type === "text") {
            return (
              <div
                key={part.id}
                className={messageContentClass(message.role)}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(part.content || (message.role === "assistant" ? "Thinking..." : "")) }}
              />
            );
          }
          return isVisibleTool(part.toolName || part.result?.tool_name) ? <ToolPartCard key={part.id} part={part} /> : null;
        })}
      </article>
    );
  }

  return (
    <article className={messageClass(message.role)}>
      <div
        className={messageContentClass(message.role)}
        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content || (message.role === "assistant" ? "Thinking..." : "")) }}
      />
      {message.tool_results?.length ? <ToolTimeline results={message.tool_results} /> : null}
    </article>
  );
}

function ToolPartCard({ part }: { part: Extract<MessagePart, { type: "tool" }> }) {
  const result = part.result;
  const title = result?.preview || `${part.status === "running" ? "Calling" : "Called"} ${part.toolName || result?.tool_name || "tool"}${result?.path ? ` ${result.path}` : ""}`;
  const body = result ? (result.error ? { error: result.error, data: result.data } : result.data ?? result.input) : { input: part.input };
  return <ToolDetails title={title} body={body} inline />;
}

function ToolTimeline({ results }: { results: ToolResult[] }) {
  const visibleResults = results.filter((result) => isVisibleTool(result.tool_name));
  if (!visibleResults.length) return null;
  return (
    <div className={ui.tools}>
      {visibleResults.map((result, index) => (
        <ToolDetails
          key={`${result.tool_name}-${index}`}
          title={result.preview || `${result.tool_name || "tool"}${result.path ? ` ${result.path}` : ""}`}
          body={result.error ? { error: result.error, data: result.data } : result.data ?? result.input}
        />
      ))}
    </div>
  );
}

function ToolDetails({ title, body, inline = false }: { title: string; body: unknown; inline?: boolean }) {
  return (
    <details className={cn(ui.tool, inline && ui.inlineTool)}>
      <summary className={ui.toolSummary}>
        <span className={ui.toolLabel}>
          <ChevronRight className={cn(ui.toolChevron, "block group-open:hidden")} size={14} strokeWidth={2.4} aria-hidden="true" />
          <ChevronDown className={cn(ui.toolChevron, "hidden group-open:block")} size={14} strokeWidth={2.4} aria-hidden="true" />
          <span className={ui.toolTitle}>{title}</span>
        </span>
      </summary>
      <pre className={ui.toolPre}>{safeJson(body)}</pre>
    </details>
  );
}

function isVisibleTool(toolName?: string): boolean {
  return toolName !== "operation_search";
}

function messageClass(role: Role): string {
  return cn("mb-[18px]", role === "user" && "flex justify-end");
}

function messageContentClass(role: Role): string {
  return cn(
    "max-w-full rounded-[18px] px-3.5 py-[11px] text-sm leading-[1.6] [overflow-wrap:anywhere]",
    role === "user"
      ? "max-w-[86%] rounded-br-[5px] bg-[var(--foa-accent)] text-[var(--foa-accent-fg)]"
      : "rounded-none bg-transparent px-0 py-0.5 text-[var(--foa-fg)]",
  );
}
