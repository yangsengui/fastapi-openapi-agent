import { LoaderCircle, Menu, PenLine, SendHorizontal, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

type ThemePreset = "default" | "ocean";

type WidgetConfig = {
  baseUrl: string;
  title: string;
  description: string;
  theme: ThemePreset;
  mode: "floating" | "embedded";
};

type Role = "user" | "assistant";

type OperationHit = {
  method: string;
  path: string;
  operation_id?: string;
  summary?: string;
  parameters?: string[];
  request_body?: boolean;
  responses?: string[];
};

type ToolResult = {
  tool_name?: string;
  ok?: boolean;
  method?: string;
  path?: string;
  status?: number;
  content_type?: string;
  input?: Record<string, unknown>;
  data?: unknown;
  preview?: string;
  error?: string;
};

type MessagePart =
  | { type: "text"; id: string; content: string }
  | { type: "tool"; id: string; toolCallId: string; toolName?: string; status: "running" | "done" | "error"; input?: Record<string, unknown>; result?: ToolResult };

type Message = {
  id: string;
  role: Role;
  content: string;
  parts?: MessagePart[];
  operations?: OperationHit[];
  tool_results?: ToolResult[];
};

type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
};

type StreamEvent = {
  type?: string;
  id?: string;
  delta?: string;
  toolCallId?: string;
  toolName?: string;
  input?: Record<string, unknown>;
  output?: ToolResult;
  errorText?: string;
  response?: {
    answer?: string;
    operations?: OperationHit[];
    tool_results?: ToolResult[];
    toolResults?: ToolResult[];
  };
};

const THEMES = {
  default: {
    panel: "#fbfaf7",
    fg: "#1f2328",
    muted: "#77736c",
    accent: "#1f2328",
    accentFg: "#ffffff",
    soft: "rgba(31,35,40,0.06)",
    border: "rgba(31,35,40,0.10)",
  },
  ocean: {
    panel: "#f6fffd",
    fg: "#083f3b",
    muted: "#4f766f",
    accent: "#0f766e",
    accentFg: "#ecfeff",
    soft: "rgba(15,118,110,0.08)",
    border: "rgba(15,118,110,0.16)",
  },
} as const;

const PROMPTS = [
  "请调用接口列出所有 items",
  "搜索创建资源相关接口",
  "调用健康检查接口",
  "解释完整调用链条",
];

export function AgentApp() {
  const config = useMemo(readConfig, []);
  const theme = THEMES[config.theme];
  const storageKey = `foa:spa:conversations:${config.baseUrl}`;
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations(storageKey));
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const active = conversations.find((item) => item.id === activeId) || null;
  const messages = active?.messages || [];
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 156)}px`;
  }, [draft]);

  const updateConversations = (updater: (items: Conversation[]) => Conversation[]) => {
    const base = latestConversations.length || conversations.length ? latestConversations : conversations;
    const next = updater(base);
    saveConversations(storageKey, next);
    setConversations(next);
  };

  const ensureConversation = (firstMessage?: string): string => {
    if (activeId) return activeId;
    const id = uid("conv");
    const conversation: Conversation = {
      id,
      title: titleFromPrompt(firstMessage || "New chat"),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };
    updateConversations((items) => [conversation, ...items].slice(0, 30));
    setActiveId(id);
    return id;
  };

  const appendMessage = (conversationId: string, message: Message) => {
    updateConversations((items) => items.map((item) => item.id === conversationId ? {
      ...item,
      updatedAt: Date.now(),
      title: item.title === "New chat" && message.role === "user" ? titleFromPrompt(message.content) : item.title,
      messages: [...item.messages, message],
    } : item));
    requestAnimationFrame(scrollToBottom);
  };

  const patchMessage = (conversationId: string, messageId: string, patch: Partial<Message>) => {
    updateConversations((items) => items.map((item) => item.id === conversationId ? {
      ...item,
      updatedAt: Date.now(),
      messages: item.messages.map((message) => message.id === messageId ? { ...message, ...patch } : message),
    } : item));
    requestAnimationFrame(scrollToBottom);
  };

  const startNew = () => {
    setActiveId(null);
    setDrawerOpen(false);
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    const conversationId = ensureConversation(text);
    appendMessage(conversationId, { id: uid("user"), role: "user", content: text });
    const assistantId = uid("assistant");
    appendMessage(conversationId, { id: assistantId, role: "assistant", content: "", parts: [], tool_results: [] });
    setBusy(true);
    try {
      await streamChat(config.baseUrl, text, conversationHistory(conversations, conversationId), (event) => {
        applyStreamEvent(event, conversationId, assistantId, patchMessage);
      });
    } catch {
      const data = await jsonChat(config.baseUrl, text, conversationHistory(conversations, conversationId));
      patchMessage(conversationId, assistantId, {
        content: data.answer || "No answer returned.",
        parts: [
          { type: "text", id: "fallback-text", content: data.answer || "No answer returned." },
          ...(data.tool_results || data.toolResults || []).map((result: ToolResult, index: number): MessagePart => ({
            type: "tool",
            id: `fallback-tool-${index}`,
            toolCallId: `fallback-tool-${index}`,
            toolName: result.tool_name,
            status: result.ok === false ? "error" : "done",
            result,
          })),
        ],
        operations: data.operations || [],
        tool_results: data.tool_results || data.toolResults || [],
      });
    } finally {
      setBusy(false);
    }
  };

  const selectPrompt = (prompt: string) => {
    setDraft(prompt);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const rootStyle = {
    "--foa-panel": theme.panel,
    "--foa-fg": theme.fg,
    "--foa-muted": theme.muted,
    "--foa-accent": theme.accent,
    "--foa-accent-fg": theme.accentFg,
    "--foa-soft": theme.soft,
    "--foa-border": theme.border,
  } as CSSProperties;

  const empty = messages.length === 0;

  function scrollToBottom() {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }

  return (
    <div className={`foa-app foa-${config.mode}`} style={rootStyle}>
      <header className="foa-header">
        <button className="foa-icon-button" type="button" aria-label="Toggle history" onClick={() => setDrawerOpen((value) => !value)}>
          <Menu size={20} strokeWidth={2.25} />
        </button>
        <div className="foa-title-block">
          <span className="foa-kicker">OpenAPI-aware</span>
          <strong>{config.title}</strong>
        </div>
        <button className="foa-icon-button" type="button" aria-label="New chat" onClick={startNew}>
          <PenLine size={19} strokeWidth={2.25} />
        </button>
        {config.mode === "floating" ? (
          <button className="foa-icon-button" type="button" aria-label="Close" onClick={() => window.parent?.postMessage({ type: "foa-widget-close" }, "*")}>
            <X size={20} strokeWidth={2.25} />
          </button>
        ) : null}
      </header>

      <aside className={`foa-history ${drawerOpen ? "foa-history-open" : ""}`}>
        <div className="foa-history-head">
          <span>Conversations</span>
          <button className="foa-icon-button" type="button" aria-label="Close history" onClick={() => setDrawerOpen(false)}>
            <X size={18} strokeWidth={2.25} />
          </button>
        </div>
        <div className="foa-history-list">
          {conversations.length === 0 ? <div className="foa-history-empty">No conversations yet.</div> : null}
          {conversations.map((conversation) => (
            <button key={conversation.id} className={`foa-history-item ${conversation.id === activeId ? "foa-active" : ""}`} type="button" onClick={() => { setActiveId(conversation.id); setDrawerOpen(false); }}>
              <span>{conversation.title}</span>
              <small>{relativeTime(conversation.updatedAt)}</small>
            </button>
          ))}
        </div>
      </aside>

      <main className="foa-main">
        {empty ? (
          <section className="foa-hero">
            <div className="foa-hero-eyebrow"><Sparkles size={14} strokeWidth={2.4} /> OpenAPI Agent Runtime</div>
            <h1>{greeting(config.title)}</h1>
            <p>{config.description}</p>
            <div className="foa-prompts">
              {PROMPTS.map((prompt) => <button key={prompt} type="button" onClick={() => selectPrompt(prompt)}>{prompt}</button>)}
            </div>
          </section>
        ) : (
          <section ref={scrollRef} className="foa-messages">
            {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
          </section>
        )}
      </main>

      <form className="foa-composer" onSubmit={submit}>
        <div className="foa-composer-shell">
          <textarea ref={textareaRef} value={draft} rows={1} placeholder="Ask about the API, or ask the agent to call an endpoint..." aria-label="Message" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void submit();
            }
          }} />
          <div className="foa-composer-footer">
            <span>Enter to send · Shift Enter for newline</span>
            <button className="foa-send-button" type="submit" disabled={busy || !draft.trim()} aria-label={busy ? "Sending" : "Send message"}>
              {busy ? <LoaderCircle className="foa-spin" size={18} strokeWidth={2.4} /> : <SendHorizontal size={18} strokeWidth={2.4} />}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.parts?.length) {
    return (
      <article className={`foa-message foa-message-${message.role}`}>
        {message.parts.map((part) => part.type === "text" ? (
          <div key={part.id} className="foa-message-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(part.content || (message.role === "assistant" ? "Thinking..." : "")) }} />
        ) : (
          <ToolPartCard key={part.id} part={part} />
        ))}
        {message.operations?.length ? <OperationSummary operations={message.operations} /> : null}
      </article>
    );
  }

  return (
    <article className={`foa-message foa-message-${message.role}`}>
      <div className="foa-message-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content || (message.role === "assistant" ? "Thinking..." : "")) }} />
      {message.tool_results?.length ? <ToolTimeline results={message.tool_results} /> : null}
      {message.operations?.length ? <OperationSummary operations={message.operations} /> : null}
    </article>
  );
}

function ToolPartCard({ part }: { part: Extract<MessagePart, { type: "tool" }> }) {
  const result = part.result;
  const title = result?.preview || `${part.status === "running" ? "Calling" : "Called"} ${part.toolName || result?.tool_name || "tool"}${result?.path ? ` ${result.path}` : ""}`;
  const body = result ? (result.error ? { error: result.error, data: result.data } : result.data ?? result.input) : { input: part.input };
  return (
    <details className={`foa-tool foa-inline-tool ${part.status === "error" || result?.ok === false ? "foa-tool-error" : ""}`}>
      <summary>
        <span>{title}</span>
        <code>{result?.status || (part.status === "running" ? "running" : part.status === "error" ? "blocked" : "ok")}</code>
      </summary>
      <pre>{safeJson(body)}</pre>
    </details>
  );
}

function ToolTimeline({ results }: { results: ToolResult[] }) {
  return (
    <div className="foa-tools">
      {results.map((result, index) => (
        <details key={`${result.tool_name}-${index}`} className={`foa-tool ${result.ok === false ? "foa-tool-error" : ""}`}>
          <summary>
            <span>{result.preview || `${result.tool_name || "tool"}${result.path ? ` ${result.path}` : ""}`}</span>
            <code>{result.status || (result.ok === false ? "blocked" : "ok")}</code>
          </summary>
          <pre>{safeJson(result.error ? { error: result.error, data: result.data } : result.data ?? result.input)}</pre>
        </details>
      ))}
    </div>
  );
}

function OperationSummary({ operations }: { operations: OperationHit[] }) {
  return (
    <details className="foa-operations">
      <summary>Read {operations.length} OpenAPI operation{operations.length === 1 ? "" : "s"}</summary>
      <div className="foa-operation-list">
        {operations.map((operation) => (
          <div key={`${operation.method}-${operation.path}`} className="foa-operation">
            <code>{operation.method}</code>
            <span>{operation.path}</span>
            <small>{operation.summary || operation.operation_id}</small>
          </div>
        ))}
      </div>
    </details>
  );
}

async function streamChat(baseUrl: string, message: string, history: { role: Role; content: string }[], onEvent: (event: StreamEvent) => void) {
  const response = await fetch(`${baseUrl}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, history }),
  });
  if (!response.ok || !response.body) throw new Error(`Stream request failed with ${response.status}`);
  await readSSE(response, onEvent);
}

async function jsonChat(baseUrl: string, message: string, history: { role: Role; content: string }[]) {
  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return response.json();
}

async function readSSE(response: Response, onEvent: (event: StreamEvent) => void) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const done = parseSSEBlock(block, onEvent);
      if (done) return;
      index = buffer.indexOf("\n\n");
    }
  }
}

function parseSSEBlock(block: string, onEvent: (event: StreamEvent) => void): boolean {
  const data = block.split(/\r?\n/u).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
  if (!data || data === "[DONE]") return true;
  try {
    onEvent(JSON.parse(data) as StreamEvent);
  } catch {
    // ignore malformed stream frames
  }
  return false;
}

function applyStreamEvent(event: StreamEvent, conversationId: string, assistantId: string, patch: (conversationId: string, messageId: string, patch: Partial<Message>) => void) {
  if (event.type === "text-start") {
    startTextPart(conversationId, assistantId, patch, event.id || "text");
    return;
  }
  if (event.type === "text-delta") {
    appendTextDelta(conversationId, assistantId, patch, event.delta || "");
    return;
  }
  if (event.type === "text-end") {
    delete activeTextPartIds[assistantId];
    return;
  }
  if (event.type === "tool-input-start" || event.type === "tool-input-available") {
    upsertTool(conversationId, assistantId, patch, event.toolCallId || event.toolName || uid("tool"), {
      tool_name: event.toolName,
      input: event.input,
      preview: event.type === "tool-input-start" ? `Preparing ${event.toolName || "tool"}` : `Calling ${event.toolName || "tool"}`,
    });
    return;
  }
  if (event.type === "tool-output-available" || event.type === "tool-output-error") {
    upsertTool(conversationId, assistantId, patch, event.toolCallId || event.toolName || uid("tool"), event.output || {
      ok: false,
      tool_name: event.toolName,
      error: event.errorText || "Tool execution failed",
    });
    return;
  }
  if (event.type === "error") {
    appendTextDelta(conversationId, assistantId, patch, event.errorText || "Stream failed.");
    return;
  }
  if (event.type === "finish" && event.response) {
    patch(conversationId, assistantId, {
      content: event.response.answer || currentMessage(conversationId, assistantId)?.content || "",
      operations: event.response.operations || [],
      tool_results: event.response.tool_results || event.response.toolResults || currentMessage(conversationId, assistantId)?.tool_results || [],
    });
  }
}

let latestConversations: Conversation[] = [];
const activeTextPartIds: Record<string, string> = {};

function currentMessage(conversationId: string, messageId: string): Message | undefined {
  return latestConversations.find((conversation) => conversation.id === conversationId)?.messages.find((message) => message.id === messageId);
}

function startTextPart(conversationId: string, messageId: string, patch: (conversationId: string, messageId: string, patch: Partial<Message>) => void, streamId: string) {
  const message = currentMessage(conversationId, messageId);
  const parts = message?.parts || [];
  const partId = `${streamId}-${parts.length}`;
  activeTextPartIds[messageId] = partId;
  patch(conversationId, messageId, { parts: [...parts, { type: "text", id: partId, content: "" }] });
}

function appendTextDelta(conversationId: string, messageId: string, patch: (conversationId: string, messageId: string, patch: Partial<Message>) => void, delta: string) {
  const message = currentMessage(conversationId, messageId);
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
  patch(conversationId, messageId, { content: `${message?.content || ""}${delta}`, parts });
}

function upsertTool(conversationId: string, messageId: string, patch: (conversationId: string, messageId: string, patch: Partial<Message>) => void, key: string, result: ToolResult) {
  const message = currentMessage(conversationId, messageId);
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

  patch(conversationId, messageId, { tool_results: results, parts });
}

function readConfig(): WidgetConfig {
  const raw = new URLSearchParams(window.location.search).get("config");
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as Partial<WidgetConfig>;
      return {
        baseUrl: String(parsed.baseUrl || "/_agent").replace(/\/$/, ""),
        title: parsed.title || "OpenAPI Agent",
        description: parsed.description || "Ask about this service's OpenAPI schema.",
        theme: parsed.theme === "ocean" ? "ocean" : "default",
        mode: parsed.mode === "embedded" ? "embedded" : "floating",
      };
    } catch {
      // fall through to defaults
    }
  }
  return { baseUrl: "/_agent", title: "OpenAPI Agent", description: "Ask about this service's OpenAPI schema.", theme: "default", mode: "floating" };
}

function loadConversations(key: string): Conversation[] {
  try {
    const items = JSON.parse(localStorage.getItem(key) || "[]") as Conversation[];
    latestConversations = items;
    return items;
  } catch {
    latestConversations = [];
    return [];
  }
}

function saveConversations(key: string, conversations: Conversation[]) {
  latestConversations = conversations;
  try {
    localStorage.setItem(key, JSON.stringify(conversations.slice(0, 30)));
  } catch {
    // ignore storage failures
  }
}

function conversationHistory(conversations: Conversation[], id: string) {
  return (conversations.find((item) => item.id === id)?.messages || [])
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({ role: message.role, content: message.content }))
    .slice(-8);
}

function renderMarkdown(value: string): string {
  let html = escapeHtml(value || "");
  html = html.replace(/```([\s\S]*?)```/g, (_match, code) => `<pre class="foa-code-block"><code>${code.replace(/^\n/, "")}</code></pre>`);
  html = renderTables(html);
  html = html.replace(/`([^`\n]+)`/g, '<code class="foa-inline-code">$1</code>');
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/^###\s+(.*)$/gm, "<h3>$1</h3>").replace(/^##\s+(.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/(?:^|\n)((?:- .*(?:\n|$))+)/g, (_match, list) => `<ul>${list.trim().split("\n").map((line: string) => `<li>${line.replace(/^- /, "")}</li>`).join("")}</ul>`);
  return html.split(/\n{2,}/).map((block) => /^<(h\d|ul|pre|div)/.test(block) ? block : `<p>${block.replace(/\n/g, "<br />")}</p>`).join("");
}

function renderTables(html: string): string {
  return html.replace(/(^|\n)((?:[^\n]*\|[^\n]*(?:\n|$))+)/g, (_whole, lead, block) => {
    const lines = String(block).trim().split(/\n/);
    if (lines.length < 2 || !lines[1].includes("---")) return lead + block;
    const split = (line: string) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
    const header = split(lines[0]);
    const rows = lines.slice(2).map(split);
    return `${lead}<div class="foa-table-wrap"><table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  });
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] || char);
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2).slice(0, 3000);
  } catch {
    return String(value);
  }
}

function uid(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function titleFromPrompt(value: string): string {
  return value.trim().slice(0, 42) || "New chat";
}

function greeting(title: string): string {
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return `${part}, ${title}`;
}

function relativeTime(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(ts).toLocaleDateString();
}
