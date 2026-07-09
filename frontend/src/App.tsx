import { ChevronDown, ChevronRight, LoaderCircle, Menu, PenLine, SendHorizontal, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

type ThemePreset = "default" | "ocean";

type WidgetConfig = {
  baseUrl: string;
  title: string;
  description: string;
  theme: ThemePreset;
  mode: "floating" | "embedded";
  requestBridge: boolean;
  parentOrigin: string | null;
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

type BridgeRequestInput = {
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

const ui = {
  app: "relative flex h-full min-h-0 w-full flex-col overflow-hidden border border-[var(--foa-border)] bg-[var(--foa-panel)] text-[var(--foa-fg)]",
  appFloating: "rounded-none shadow-[-14px_0_48px_rgba(15,23,42,0.18)]",
  appEmbedded: "rounded-none shadow-[-10px_0_36px_rgba(15,23,42,0.1)]",
  header: "flex h-12 shrink-0 items-center gap-2.5 border-b border-[var(--foa-border)] py-0 pr-2.5 pl-2",
  iconButton: "grid h-[34px] w-[34px] cursor-pointer place-items-center rounded-[10px] border-0 bg-transparent text-[var(--foa-fg)] transition-[background,color,transform] duration-150 hover:bg-[var(--foa-soft)] active:translate-y-px",
  titleBlock: "flex min-w-0 flex-1 flex-col leading-[1.1]",
  title: "truncate text-[15px]",
  kicker: "text-[10px] font-bold tracking-[0.14em] text-[var(--foa-accent)] uppercase opacity-[0.85]",
  history: "absolute top-12 bottom-0 left-0 z-40 flex w-[78%] max-w-[260px] flex-col border-r border-[var(--foa-border)] bg-[var(--foa-panel)] shadow-[6px_0_28px_rgba(15,23,42,0.08)] transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]",
  historyHead: "flex items-center justify-between px-3 py-2.5 text-[11px] font-bold tracking-[0.1em] text-[var(--foa-muted)] uppercase",
  historyList: "flex-1 overflow-auto px-2 py-1.5",
  historyEmpty: "px-3 py-4 text-[13px] text-[var(--foa-muted)]",
  historyItem: "flex w-full cursor-pointer flex-col gap-0.5 rounded-[10px] border-0 bg-transparent px-2.5 py-2 text-left text-[var(--foa-fg)] hover:bg-[var(--foa-soft)]",
  historyTitle: "truncate",
  historyTime: "text-[var(--foa-muted)]",
  main: "min-h-0 flex-1",
  hero: "flex h-full flex-col justify-center overflow-auto px-5 py-6",
  heroEyebrow: "mb-2.5 inline-flex items-center gap-1.5 text-[10px] font-bold tracking-[0.14em] text-[var(--foa-accent)] uppercase",
  heroTitle: "m-0 mb-2 text-[30px] leading-[1.1] font-medium tracking-[-0.02em] max-sm:text-2xl",
  heroDescription: "m-0 mb-5 text-[15px] leading-[1.6] text-[var(--foa-muted)]",
  prompts: "flex flex-wrap gap-2",
  promptButton: "cursor-pointer rounded-full border border-[var(--foa-border)] bg-[rgba(255,255,255,0.55)] px-3 py-2 text-xs font-semibold text-[var(--foa-fg)]",
  messages: "h-full overflow-auto px-[18px] pt-4 pb-2",
  tools: "my-1.5 grid gap-[3px]",
  tool: "group overflow-hidden rounded-lg border-0 bg-transparent",
  inlineTool: "my-1",
  toolSummary: "flex cursor-pointer list-none items-center gap-2 border-b-0 py-1 text-sm leading-[1.6] font-bold text-[var(--foa-muted)] [&::-webkit-details-marker]:hidden",
  toolLabel: "inline-flex min-w-0 items-center gap-1.5",
  toolChevron: "shrink-0 text-[var(--foa-muted)]",
  toolTitle: "flex-1 truncate",
  toolPre: "ml-[13px] max-h-[220px] overflow-auto border-l-2 border-[var(--foa-border)] bg-[rgba(255,255,255,0.45)] px-2.5 py-2 font-mono text-[11px] leading-[1.45] whitespace-pre-wrap text-[var(--foa-muted)]",
  composer: "shrink-0 border-t border-[var(--foa-border)] bg-gradient-to-t from-[rgba(251,250,247,0.96)] to-[rgba(251,250,247,0.78)] px-3.5 pt-3 pb-3.5 max-sm:p-2.5",
  composerShell: "grid w-full gap-[7px] rounded-[22px] border border-[var(--foa-border)] bg-[rgba(255,255,255,0.86)] pt-2.5 pr-2.5 pb-2 pl-[13px] shadow-[0_10px_32px_rgba(15,23,42,0.07)] transition-[border-color,box-shadow,background] duration-150 focus-within:border-[rgba(31,35,40,0.26)] focus-within:bg-[rgba(255,255,255,0.96)] focus-within:shadow-[0_0_0_3px_var(--foa-soft),0_14px_40px_rgba(15,23,42,0.1)] max-sm:rounded-[20px] max-sm:pt-[9px] max-sm:pr-[9px] max-sm:pb-2 max-sm:pl-3",
  textarea: "max-h-[156px] min-h-7 w-full resize-none overflow-y-auto border-0 bg-transparent px-0.5 pt-1 pb-0 text-sm leading-[1.5] text-[var(--foa-fg)] outline-none placeholder:text-[var(--foa-muted)] placeholder:opacity-80",
  composerFooter: "flex items-center justify-between gap-2.5",
  composerHint: "truncate text-[11px] leading-[1.2] text-[var(--foa-muted)] max-sm:hidden",
  sendButton: "inline-grid h-[34px] w-[34px] shrink-0 cursor-pointer place-items-center rounded-[14px] border border-transparent bg-[var(--foa-accent)] text-[var(--foa-accent-fg)] shadow-[0_8px_22px_rgba(15,23,42,0.16)] transition-[transform,box-shadow,opacity] duration-150 enabled:hover:-translate-y-px enabled:hover:shadow-[0_11px_26px_rgba(15,23,42,0.2)] enabled:active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none",
};

const markdown = {
  paragraph: "mt-0 mb-2 last:mb-0",
  heading: "mt-2.5 mb-1.5 text-[15px]",
  list: "mt-0 mb-2 list-disc pl-[18px] last:mb-0",
  inlineCode: "rounded-[5px] bg-[var(--foa-soft)] px-[5px] py-px font-mono text-[90%]",
  codeBlock: "m-0 overflow-auto whitespace-pre-wrap font-mono",
  tableWrap: "my-2 max-w-full overflow-x-auto rounded-xl border border-[var(--foa-border)] bg-[rgba(255,255,255,0.5)]",
  table: "w-full border-collapse text-[13px]",
  cell: "border border-[var(--foa-border)] px-[9px] py-1.5 text-left",
};

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
      await streamChat(config, text, conversationHistory(conversations, conversationId), (event) => {
        applyStreamEvent(event, conversationId, assistantId, patchMessage);
      });
    } catch {
      const data = await jsonChat(config, text, conversationHistory(conversations, conversationId));
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
  const canClose = config.mode === "floating" || window.parent !== window;

  function scrollToBottom() {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }

  return (
    <div className={cn(ui.app, config.mode === "floating" ? ui.appFloating : ui.appEmbedded)} style={rootStyle}>
      <header className={ui.header}>
        <button className={ui.iconButton} type="button" aria-label="Toggle history" onClick={() => setDrawerOpen((value) => !value)}>
          <Menu size={20} strokeWidth={2.25} />
        </button>
        <div className={ui.titleBlock}>
          <span className={ui.kicker}>OpenAPI-aware</span>
          <strong className={ui.title}>{config.title}</strong>
        </div>
        <button className={ui.iconButton} type="button" aria-label="New chat" onClick={startNew}>
          <PenLine size={19} strokeWidth={2.25} />
        </button>
        {canClose ? (
          <button className={ui.iconButton} type="button" aria-label="Close sidebar" onClick={() => window.parent?.postMessage({ type: "foa-widget-close" }, "*")}>
            <X size={20} strokeWidth={2.25} />
          </button>
        ) : null}
      </header>

      <aside className={cn(ui.history, drawerOpen ? "translate-x-0" : "-translate-x-[105%]")}>
        <div className={ui.historyHead}>
          <span>Conversations</span>
          <button className={ui.iconButton} type="button" aria-label="Close history" onClick={() => setDrawerOpen(false)}>
            <X size={18} strokeWidth={2.25} />
          </button>
        </div>
        <div className={ui.historyList}>
          {conversations.length === 0 ? <div className={ui.historyEmpty}>No conversations yet.</div> : null}
          {conversations.map((conversation) => (
            <button key={conversation.id} className={cn(ui.historyItem, conversation.id === activeId && "bg-[var(--foa-soft)]")} type="button" onClick={() => { setActiveId(conversation.id); setDrawerOpen(false); }}>
              <span className={ui.historyTitle}>{conversation.title}</span>
              <small className={ui.historyTime}>{relativeTime(conversation.updatedAt)}</small>
            </button>
          ))}
        </div>
      </aside>

      <main className={ui.main}>
        {empty ? (
          <section className={ui.hero}>
            <div className={ui.heroEyebrow}><Sparkles size={14} strokeWidth={2.4} /> OpenAPI Agent Runtime</div>
            <h1 className={ui.heroTitle}>{greeting(config.title)}</h1>
            <p className={ui.heroDescription}>{config.description}</p>
            <div className={ui.prompts}>
              {PROMPTS.map((prompt) => <button key={prompt} className={ui.promptButton} type="button" onClick={() => selectPrompt(prompt)}>{prompt}</button>)}
            </div>
          </section>
        ) : (
          <section ref={scrollRef} className={ui.messages}>
            {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
          </section>
        )}
      </main>

      <form className={ui.composer} onSubmit={submit}>
        <div className={ui.composerShell}>
          <textarea ref={textareaRef} className={ui.textarea} value={draft} rows={1} placeholder="Ask about the API, or ask the agent to call an endpoint..." aria-label="Message" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void submit();
            }
          }} />
          <div className={ui.composerFooter}>
            <span className={ui.composerHint}>Enter to send · Shift Enter for newline</span>
            <button className={ui.sendButton} type="submit" disabled={busy || !draft.trim()} aria-label={busy ? "Sending" : "Send message"}>
              {busy ? <LoaderCircle className="animate-spin" size={18} strokeWidth={2.4} /> : <SendHorizontal size={18} strokeWidth={2.4} />}
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
      <article className={messageClass(message.role)}>
        {message.parts.map((part) => {
          if (part.type === "text") {
            return <div key={part.id} className={messageContentClass(message.role)} dangerouslySetInnerHTML={{ __html: renderMarkdown(part.content || (message.role === "assistant" ? "Thinking..." : "")) }} />;
          }
          return isVisibleTool(part.toolName || part.result?.tool_name) ? <ToolPartCard key={part.id} part={part} /> : null;
        })}
      </article>
    );
  }

  return (
    <article className={messageClass(message.role)}>
      <div className={messageContentClass(message.role)} dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content || (message.role === "assistant" ? "Thinking..." : "")) }} />
      {message.tool_results?.length ? <ToolTimeline results={message.tool_results} /> : null}
    </article>
  );
}

function ToolPartCard({ part }: { part: Extract<MessagePart, { type: "tool" }> }) {
  const result = part.result;
  const title = result?.preview || `${part.status === "running" ? "Calling" : "Called"} ${part.toolName || result?.tool_name || "tool"}${result?.path ? ` ${result.path}` : ""}`;
  const body = result ? (result.error ? { error: result.error, data: result.data } : result.data ?? result.input) : { input: part.input };
  return (
    <details className={cn(ui.tool, ui.inlineTool)}>
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

function ToolTimeline({ results }: { results: ToolResult[] }) {
  const visibleResults = results.filter((result) => isVisibleTool(result.tool_name));
  if (!visibleResults.length) return null;
  return (
    <div className={ui.tools}>
      {visibleResults.map((result, index) => (
        <details key={`${result.tool_name}-${index}`} className={ui.tool}>
          <summary className={ui.toolSummary}>
            <span className={ui.toolLabel}>
              <ChevronRight className={cn(ui.toolChevron, "block group-open:hidden")} size={14} strokeWidth={2.4} aria-hidden="true" />
              <ChevronDown className={cn(ui.toolChevron, "hidden group-open:block")} size={14} strokeWidth={2.4} aria-hidden="true" />
              <span className={ui.toolTitle}>{result.preview || `${result.tool_name || "tool"}${result.path ? ` ${result.path}` : ""}`}</span>
            </span>
          </summary>
          <pre className={ui.toolPre}>{safeJson(result.error ? { error: result.error, data: result.data } : result.data ?? result.input)}</pre>
        </details>
      ))}
    </div>
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

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

async function streamChat(config: WidgetConfig, message: string, history: { role: Role; content: string }[], onEvent: (event: StreamEvent) => void) {
  const body = JSON.stringify({ message, history });
  const request = {
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
    method: "POST",
    headers: request.headers,
    body,
  });
  if (!response.ok || !response.body) throw new Error(`Stream request failed with ${response.status}`);
  await readSSE(response, onEvent);
}

async function jsonChat(config: WidgetConfig, message: string, history: { role: Role; content: string }[]) {
  const body = JSON.stringify({ message, history });
  const request = {
    url: `${config.baseUrl}/chat`,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  };

  if (config.requestBridge) {
    const response = await bridgeRequest(config, request);
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    return JSON.parse(response.body || "{}");
  }

  const response = await fetch(request.url, {
    method: "POST",
    headers: request.headers,
    body,
  });
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return response.json();
}

async function bridgeRequest(config: WidgetConfig, request: BridgeRequestInput, onChunk?: (chunk: string) => void): Promise<BridgeResponse> {
  if (!config.requestBridge || window.parent === window) throw new Error("OpenAgent request bridge is unavailable.");

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

async function readSSE(response: Response, onEvent: (event: StreamEvent) => void) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser(onEvent);
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    if (parser.push(decoder.decode(chunk.value, { stream: true }))) return;
  }
  parser.push(decoder.decode());
}

function createSSEParser(onEvent: (event: StreamEvent) => void): { push: (chunk: string) => boolean } {
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
        requestBridge: parsed.requestBridge === true,
        parentOrigin: typeof parsed.parentOrigin === "string" ? parsed.parentOrigin : null,
      };
    } catch {
      // fall through to defaults
    }
  }
  return { baseUrl: "/_agent", title: "OpenAPI Agent", description: "Ask about this service's OpenAPI schema.", theme: "default", mode: "floating", requestBridge: false, parentOrigin: null };
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
  html = html.replace(/```([\s\S]*?)```/g, (_match, code) => `<pre class="${markdown.codeBlock}"><code>${code.replace(/^\n/, "")}</code></pre>`);
  html = renderTables(html);
  html = html.replace(/`([^`\n]+)`/g, `<code class="${markdown.inlineCode}">$1</code>`);
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/^###\s+(.*)$/gm, `<h3 class="${markdown.heading}">$1</h3>`).replace(/^##\s+(.*)$/gm, `<h2 class="${markdown.heading}">$1</h2>`);
  html = html.replace(/(?:^|\n)((?:- .*(?:\n|$))+)/g, (_match, list) => `<ul class="${markdown.list}">${list.trim().split("\n").map((line: string) => `<li>${line.replace(/^- /, "")}</li>`).join("")}</ul>`);
  return html.split(/\n{2,}/).map((block) => /^<(h\d|ul|pre|div)/.test(block) ? block : `<p class="${markdown.paragraph}">${block.replace(/\n/g, "<br />")}</p>`).join("");
}

function renderTables(html: string): string {
  return html.replace(/(^|\n)((?:[^\n]*\|[^\n]*(?:\n|$))+)/g, (_whole, lead, block) => {
    const lines = String(block).trim().split(/\n/);
    if (lines.length < 2 || !lines[1].includes("---")) return lead + block;
    const split = (line: string) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
    const header = split(lines[0]);
    const rows = lines.slice(2).map(split);
    return `${lead}<div class="${markdown.tableWrap}"><table class="${markdown.table}"><thead><tr>${header.map((cell) => `<th class="${markdown.cell}">${cell}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td class="${markdown.cell}">${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
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
