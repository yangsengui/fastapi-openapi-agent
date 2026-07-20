import { useRef, useState } from "react";

import type { ChatHistoryItem, Conversation, Language, Message } from "../types";
import { titleFromPrompt, uid } from "../lib/utils";

const conversationLimit = 30;

export function useConversations(storageKey: string, language: Language = "en") {
  const initial = useRef<Conversation[] | null>(null);
  if (initial.current === null) initial.current = loadConversations(storageKey);

  const latest = useRef(initial.current);
  const [conversations, setConversations] = useState<Conversation[]>(initial.current);
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = conversations.find((item) => item.id === activeId) || null;

  const update = (updater: (items: Conversation[]) => Conversation[]) => {
    const next = updater(latest.current);
    latest.current = next;
    saveConversations(storageKey, next);
    setConversations(next);
  };

  const ensureConversation = (firstMessage: string): string => {
    if (activeId) return activeId;
    const id = uid("conv");
    const now = Date.now();
    update((items) => [{
      id,
      title: titleFromPrompt(firstMessage, language),
      createdAt: now,
      updatedAt: now,
      messages: [],
    }, ...items].slice(0, conversationLimit));
    setActiveId(id);
    return id;
  };

  const appendMessage = (conversationId: string, message: Message) => {
    update((items) => items.map((item) => item.id === conversationId ? {
      ...item,
      updatedAt: Date.now(),
      title: ["New chat", "新对话"].includes(item.title) && message.role === "user" ? titleFromPrompt(message.content, language) : item.title,
      messages: [...item.messages, message],
    } : item));
  };

  const patchMessage = (conversationId: string, messageId: string, patch: Partial<Message>) => {
    update((items) => items.map((item) => item.id === conversationId ? {
      ...item,
      updatedAt: Date.now(),
      messages: item.messages.map((message) => message.id === messageId ? { ...message, ...patch } : message),
    } : item));
  };

  const getMessage = (conversationId: string, messageId: string): Message | undefined =>
    latest.current.find((conversation) => conversation.id === conversationId)?.messages.find((message) => message.id === messageId);

  const getHistory = (conversationId: string | null): ChatHistoryItem[] => {
    if (!conversationId) return [];
    return (latest.current.find((item) => item.id === conversationId)?.messages || [])
      .filter((message) => message.role === "user" || message.role === "assistant")
      .map(({ role, content }) => ({ role, content }))
      .slice(-8);
  };

  return {
    conversations,
    activeId,
    active,
    setActiveId,
    startNew: () => setActiveId(null),
    ensureConversation,
    appendMessage,
    patchMessage,
    getMessage,
    getHistory,
  };
}

function loadConversations(key: string): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]") as Conversation[];
  } catch {
    return [];
  }
}

function saveConversations(key: string, conversations: Conversation[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(conversations.slice(0, conversationLimit)));
  } catch {
    // Conversation state remains available in memory when storage is unavailable.
  }
}
