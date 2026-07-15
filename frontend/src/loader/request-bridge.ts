import type { LoaderConfig, LoaderRequestInput } from "./types";

type BridgeRequestMessage = {
  type?: string;
  id?: string;
  request?: LoaderRequestInput;
};

type BridgeResponseMessage = {
  type: "foa-response-complete" | "foa-response-chunk" | "foa-response-end" | "foa-response-error";
  id: string;
  status?: number;
  ok?: boolean;
  headers?: Record<string, string>;
  body?: string;
  chunk?: string;
  error?: string;
};

export function setupWidgetMessages(
  iframe: HTMLIFrameElement,
  config: LoaderConfig,
  src: string,
  baseUrl: string,
  onClose?: () => void,
): void {
  const request = typeof config.request === "function" ? config.request : null;
  const targetOrigin = resolveTargetOrigin(src);

  window.addEventListener("message", (event) => {
    if (event.source !== iframe.contentWindow || !event.data || typeof event.data !== "object") return;
    const data = event.data as BridgeRequestMessage;
    if (data.type === "foa-widget-close") {
      onClose?.();
      return;
    }
    if (data.type !== "foa-request" || !request) return;
    void handleBridgeRequest(data, request, iframe, targetOrigin, baseUrl);
  });
}

async function handleBridgeRequest(
  message: BridgeRequestMessage,
  request: (input: LoaderRequestInput) => Response | Promise<Response>,
  iframe: HTMLIFrameElement,
  targetOrigin: string,
  baseUrl: string,
): Promise<void> {
  const id = typeof message.id === "string" ? message.id : "";
  const input = message.request;
  if (!id || !input || typeof input.url !== "string") return;

  const post = (payload: BridgeResponseMessage): void => {
    iframe.contentWindow?.postMessage(payload, targetOrigin);
  };

  try {
    if (!isAllowedBridgeUrl(input.url, baseUrl)) {
      post({ type: "foa-response-error", id, error: "Blocked request outside OpenAgent baseUrl." });
      return;
    }

    const response = await request({
      url: input.url,
      method: input.method || "GET",
      headers: normalizeHeaders(input.headers),
      body: input.body ?? null,
      stream: input.stream === true,
    });
    if (!response || typeof response.text !== "function") {
      post({ type: "foa-response-error", id, error: "OpenAgent request must return a fetch Response." });
      return;
    }

    const status = typeof response.status === "number" ? response.status : 200;
    const ok = "ok" in response ? response.ok : status < 400;
    const headers = serializeHeaders(response.headers);

    if (!ok) {
      const body = await response.text();
      post({ type: "foa-response-error", id, status, ok, headers, body, error: `Request failed with ${status}.` });
      return;
    }
    if (input.stream) {
      await streamBridgeResponse(response, (chunk) => post({ type: "foa-response-chunk", id, chunk }));
      post({ type: "foa-response-end", id, status, ok, headers });
      return;
    }
    post({ type: "foa-response-complete", id, status, ok, headers, body: await response.text() });
  } catch (error) {
    post({ type: "foa-response-error", id, error: error instanceof Error ? error.message : "OpenAgent request failed." });
  }
}

async function streamBridgeResponse(response: Response, onChunk: (chunk: string) => void): Promise<void> {
  if (!response.body) {
    const text = await response.text();
    if (text) onChunk(text);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    onChunk(decoder.decode(chunk.value, { stream: true }));
  }
  const rest = decoder.decode();
  if (rest) onChunk(rest);
}

function serializeHeaders(headers: Response["headers"] | undefined): Record<string, string> {
  const result: Record<string, string> = {};
  headers?.forEach((value, name) => {
    result[name] = value;
  });
  return result;
}

function normalizeHeaders(headers: LoaderRequestInput["headers"]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [name, value] of Object.entries(headers || {})) {
    if (value !== undefined && value !== null) result[name] = String(value);
  }
  return result;
}

function resolveTargetOrigin(src: string): string {
  try {
    return new URL(src, window.location.href).origin;
  } catch {
    return "*";
  }
}

function isAllowedBridgeUrl(url: string, baseUrl: string): boolean {
  try {
    const requestUrl = new URL(url, window.location.href);
    const base = new URL(baseUrl, window.location.href);
    const basePath = base.pathname.replace(/\/$/u, "");
    return requestUrl.origin === base.origin && (requestUrl.pathname === basePath || requestUrl.pathname.startsWith(`${basePath}/`));
  } catch {
    return false;
  }
}
