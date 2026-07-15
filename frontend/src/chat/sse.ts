import type { StreamEvent } from "../types";

export async function readSSE(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.body) throw new Error("Stream response body is unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser(onEvent);
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    if (parser.push(decoder.decode(chunk.value, { stream: true }))) return;
  }
  parser.push(decoder.decode());
}

export function createSSEParser(onEvent: (event: StreamEvent) => void): { push: (chunk: string) => boolean } {
  let buffer = "";
  let closed = false;
  return {
    push(chunk: string) {
      if (closed) return true;
      buffer += chunk;
      let index = buffer.indexOf("\n\n");
      while (index >= 0) {
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        closed = parseSSEBlock(block, onEvent);
        if (closed) return true;
        index = buffer.indexOf("\n\n");
      }
      return false;
    },
  };
}

function parseSSEBlock(block: string, onEvent: (event: StreamEvent) => void): boolean {
  const data = block
    .split(/\r?\n/u)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data || data === "[DONE]") return true;
  try {
    onEvent(JSON.parse(data) as StreamEvent);
  } catch {
    // Ignore malformed stream frames and continue reading the response.
  }
  return false;
}
