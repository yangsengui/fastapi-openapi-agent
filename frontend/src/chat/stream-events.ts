import type { Message, MessagePart, StreamEvent, ToolResult } from "../types";
import { uid } from "../lib/utils";

type MessagePatch = (messageId: string, patch: Partial<Message>) => void;
type MessageLookup = (messageId: string) => Message | undefined;

export function createStreamEventHandler(getMessage: MessageLookup, patchMessage: MessagePatch) {
  const activeTextPartIds: Record<string, string> = {};

  return (event: StreamEvent, assistantId: string): void => {
    if (event.type === "text-start") {
      startTextPart(getMessage, patchMessage, assistantId, event.id || "text", activeTextPartIds);
      return;
    }
    if (event.type === "text-delta") {
      appendTextDelta(getMessage, patchMessage, assistantId, event.delta || "", activeTextPartIds);
      return;
    }
    if (event.type === "text-end") {
      delete activeTextPartIds[assistantId];
      return;
    }
    if (event.type === "tool-input-start" || event.type === "tool-input-available") {
      upsertTool(getMessage, patchMessage, assistantId, event.toolCallId || event.toolName || uid("tool"), {
        tool_name: event.toolName,
        input: event.input,
        preview: event.type === "tool-input-start" ? `Preparing ${event.toolName || "tool"}` : `Calling ${event.toolName || "tool"}`,
      });
      return;
    }
    if (event.type === "tool-output-available" || event.type === "tool-output-error") {
      upsertTool(getMessage, patchMessage, assistantId, event.toolCallId || event.toolName || uid("tool"), event.output || {
        ok: false,
        tool_name: event.toolName,
        error: event.errorText || "Tool execution failed",
      });
      return;
    }
    if (event.type === "error") {
      appendTextDelta(getMessage, patchMessage, assistantId, event.errorText || "Stream failed.", activeTextPartIds);
      return;
    }
    if (event.type === "finish" && event.response) {
      const current = getMessage(assistantId);
      patchMessage(assistantId, {
        content: event.response.answer || current?.content || "",
        operations: event.response.operations || [],
        tool_results: event.response.tool_results || event.response.toolResults || current?.tool_results || [],
      });
    }
  };
}

function startTextPart(
  getMessage: MessageLookup,
  patchMessage: MessagePatch,
  messageId: string,
  streamId: string,
  activeTextPartIds: Record<string, string>,
): void {
  const parts = getMessage(messageId)?.parts || [];
  const partId = `${streamId}-${parts.length}`;
  activeTextPartIds[messageId] = partId;
  patchMessage(messageId, { parts: [...parts, { type: "text", id: partId, content: "" }] });
}

function appendTextDelta(
  getMessage: MessageLookup,
  patchMessage: MessagePatch,
  messageId: string,
  delta: string,
  activeTextPartIds: Record<string, string>,
): void {
  const message = getMessage(messageId);
  const parts = [...(message?.parts || [])];
  let partId = activeTextPartIds[messageId];
  if (!partId) {
    partId = `text-${parts.length}`;
    activeTextPartIds[messageId] = partId;
    parts.push({ type: "text", id: partId, content: "" });
  }
  const index = parts.findIndex((part) => part.type === "text" && part.id === partId);
  if (index >= 0 && parts[index].type === "text") {
    parts[index] = { ...parts[index], content: `${parts[index].content}${delta}` };
  }
  patchMessage(messageId, { content: `${message?.content || ""}${delta}`, parts });
}

function upsertTool(
  getMessage: MessageLookup,
  patchMessage: MessagePatch,
  messageId: string,
  key: string,
  result: ToolResult,
): void {
  const message = getMessage(messageId);
  const existing = message?.tool_results || [];
  const index = existing.findIndex((item) => String(item.input?.__toolCallId || item.tool_name || "") === key);
  const next = { ...result, input: { ...(result.input || {}), __toolCallId: key } };
  const results = [...existing];
  if (index >= 0) results[index] = next;
  else results.push(next);

  const parts = [...(message?.parts || [])];
  const partIndex = parts.findIndex((part) => part.type === "tool" && part.toolCallId === key);
  const toolPart: MessagePart = {
    type: "tool",
    id: `tool-${key}`,
    toolCallId: key,
    toolName: result.tool_name,
    status: result.ok === false ? "error" : result.data !== undefined || result.error ? "done" : "running",
    input: result.input,
    result: result.data !== undefined || result.error ? next : undefined,
  };
  if (partIndex >= 0) parts[partIndex] = toolPart;
  else parts.push(toolPart);

  patchMessage(messageId, { tool_results: results, parts });
}
