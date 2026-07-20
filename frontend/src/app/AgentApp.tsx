import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { jsonChat, streamChat } from "../chat/client";
import { createStreamEventHandler } from "../chat/stream-events";
import { AgentHeader } from "../components/AgentHeader";
import { Composer } from "../components/Composer";
import { ConversationDrawer } from "../components/ConversationDrawer";
import { EmptyState } from "../components/EmptyState";
import { MessageList } from "../components/MessageList";
import { useConversations } from "../hooks/use-conversations";
import type { MessagePart, ToolResult } from "../types";
import { uid, cn } from "../lib/utils";
import { readConfig } from "./config";
import { getCopy } from "./i18n";
import { ui } from "./styles";
import { themeStyle } from "./theme";

export function AgentApp() {
  const [config] = useState(readConfig);
  const copy = getCopy(config.language);
  const store = useConversations(`foa:spa:conversations:${config.baseUrl}:${config.language}`, config.language);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const messages = store.active?.messages || [];

  useEffect(() => {
    document.documentElement.lang = config.language;
  }, [config.language]);

  const scrollToBottom = () => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;

    const history = store.getHistory(store.activeId);
    const conversationId = store.ensureConversation(text);
    const assistantId = uid("assistant");
    const patchAssistant = (messageId: string, patch: Parameters<typeof store.patchMessage>[2]) => {
      store.patchMessage(conversationId, messageId, patch);
      requestAnimationFrame(scrollToBottom);
    };
    const handleStreamEvent = createStreamEventHandler(
      (messageId) => store.getMessage(conversationId, messageId),
      patchAssistant,
      copy,
    );

    setDraft("");
    store.appendMessage(conversationId, { id: uid("user"), role: "user", content: text });
    store.appendMessage(conversationId, { id: assistantId, role: "assistant", content: "", parts: [], tool_results: [] });
    requestAnimationFrame(scrollToBottom);
    setBusy(true);

    try {
      await streamChat(config, text, history, (streamEvent) => handleStreamEvent(streamEvent, assistantId));
    } catch {
      const data = await jsonChat(config, text, history);
      const answer = data.answer || copy.noAnswer;
      patchAssistant(assistantId, {
        content: answer,
        parts: [
          { type: "text", id: "fallback-text", content: answer },
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

  const startNew = () => {
    store.startNew();
    setDrawerOpen(false);
  };

  const selectPrompt = (prompt: string) => {
    setDraft(prompt);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  return (
    <div
      className={cn(ui.app, config.mode === "floating" ? ui.appFloating : ui.appEmbedded)}
      style={themeStyle(config.theme)}
    >
      <AgentHeader
        title={config.title}
        copy={copy}
        canClose={config.mode === "floating" || window.parent !== window}
        onToggleHistory={() => setDrawerOpen((open) => !open)}
        onNewChat={startNew}
      />

      <ConversationDrawer
        conversations={store.conversations}
        activeId={store.activeId}
        open={drawerOpen}
        copy={copy}
        language={config.language}
        onClose={() => setDrawerOpen(false)}
        onSelect={(conversationId) => {
          store.setActiveId(conversationId);
          setDrawerOpen(false);
        }}
      />

      <main className={ui.main}>
        {messages.length === 0 ? (
          <EmptyState
            title={config.title}
            welcomeTitle={config.welcomeTitle}
            description={config.description}
            copy={copy}
            language={config.language}
            onSelectPrompt={selectPrompt}
          />
        ) : (
          <MessageList messages={messages} scrollRef={scrollRef} copy={copy} />
        )}
      </main>

      <Composer
        draft={draft}
        busy={busy}
        copy={copy}
        textareaRef={textareaRef}
        onDraftChange={setDraft}
        onSubmit={(event) => void submit(event)}
      />
    </div>
  );
}
