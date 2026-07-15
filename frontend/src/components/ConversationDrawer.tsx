import { X } from "lucide-react";

import { ui } from "../app/styles";
import type { Conversation } from "../types";
import { cn, relativeTime } from "../lib/utils";

type ConversationDrawerProps = {
  conversations: Conversation[];
  activeId: string | null;
  open: boolean;
  onClose: () => void;
  onSelect: (conversationId: string) => void;
};

export function ConversationDrawer({ conversations, activeId, open, onClose, onSelect }: ConversationDrawerProps) {
  return (
    <aside
      className={cn(ui.history, open ? "translate-x-0" : "-translate-x-[105%]")}
      aria-hidden={!open}
      inert={!open}
    >
      <div className={ui.historyHead}>
        <span>Conversations</span>
        <button className={ui.iconButton} type="button" aria-label="Close history" onClick={onClose}>
          <X size={18} strokeWidth={2.25} />
        </button>
      </div>
      <div className={ui.historyList}>
        {conversations.length === 0 ? <div className={ui.historyEmpty}>No conversations yet.</div> : null}
        {conversations.map((conversation) => (
          <button
            key={conversation.id}
            className={cn(ui.historyItem, conversation.id === activeId && "bg-[var(--foa-soft)]")}
            type="button"
            onClick={() => onSelect(conversation.id)}
          >
            <span className={ui.historyTitle}>{conversation.title}</span>
            <small className={ui.historyTime}>{relativeTime(conversation.updatedAt)}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}
