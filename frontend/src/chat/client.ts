import type { ChatHistoryItem, ChatResponse, StreamEvent, WidgetConfig } from "../types";
import { bridgeRequest, type BridgeRequestInput } from "./bridge";
import { createSSEParser, readSSE } from "./sse";

export async function streamChat(
  config: WidgetConfig,
  message: string,
  history: ChatHistoryItem[],
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const body = JSON.stringify({ message, history });
  const request: BridgeRequestInput = {
    url: `${config.baseUrl}/chat/stream`,
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body,
    stream: true,
  };

  if (config.requestBridge) {
    const parser = createSSEParser(onEvent);
    await bridgeRequest(config, request, (chunk) => parser.push(chunk));
    return;
  }

  const response = await fetch(request.url, {
    method: request.method,
    headers: request.headers,
    body,
  });
  if (!response.ok || !response.body) throw new Error(`Stream request failed with ${response.status}`);
  await readSSE(response, onEvent);
}

export async function jsonChat(config: WidgetConfig, message: string, history: ChatHistoryItem[]): Promise<ChatResponse> {
  const body = JSON.stringify({ message, history });
  const request: BridgeRequestInput = {
    url: `${config.baseUrl}/chat`,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  };

  if (config.requestBridge) {
    const response = await bridgeRequest(config, request);
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    return JSON.parse(response.body || "{}") as ChatResponse;
  }

  const response = await fetch(request.url, {
    method: request.method,
    headers: request.headers,
    body,
  });
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return response.json() as Promise<ChatResponse>;
}
