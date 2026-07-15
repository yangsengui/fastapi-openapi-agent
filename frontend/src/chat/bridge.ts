import type { WidgetConfig } from "../types";
import { uid } from "../lib/utils";

export type BridgeRequestInput = {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string | null;
  stream?: boolean;
};

type BridgeResponse = {
  status: number;
  ok: boolean;
  headers: Record<string, string>;
  body?: string;
};

type BridgeResponseMessage = {
  type?: string;
  id?: string;
  status?: number;
  ok?: boolean;
  headers?: Record<string, string>;
  body?: string;
  chunk?: string;
  error?: string;
};

export async function bridgeRequest(
  config: WidgetConfig,
  request: BridgeRequestInput,
  onChunk?: (chunk: string) => void,
): Promise<BridgeResponse> {
  if (!config.requestBridge || window.parent === window) {
    throw new Error("OpenAgent request bridge is unavailable.");
  }

  return new Promise((resolve, reject) => {
    const id = uid("bridge");
    const targetOrigin = config.parentOrigin || "*";
    const cleanup = () => window.removeEventListener("message", handleMessage);

    const handleMessage = (event: MessageEvent<BridgeResponseMessage>) => {
      if (event.source !== window.parent) return;
      if (config.parentOrigin && event.origin !== config.parentOrigin) return;
      const data = event.data;
      if (!data || typeof data !== "object" || data.id !== id) return;

      if (data.type === "foa-response-chunk") {
        if (data.chunk) onChunk?.(data.chunk);
        return;
      }
      if (data.type === "foa-response-end" || data.type === "foa-response-complete") {
        cleanup();
        resolve({
          status: data.status || 200,
          ok: data.ok !== false,
          headers: data.headers || {},
          body: data.body,
        });
        return;
      }
      if (data.type === "foa-response-error") {
        cleanup();
        reject(new Error(data.error || `Request failed with ${data.status || "unknown status"}.`));
      }
    };

    window.addEventListener("message", handleMessage);
    window.parent.postMessage({ type: "foa-request", id, request }, targetOrigin);
  });
}
