import { Menu, PenLine, X } from "lucide-react";

import { ui } from "../app/styles";

type AgentHeaderProps = {
  title: string;
  canClose: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
};

export function AgentHeader({ title, canClose, onToggleHistory, onNewChat }: AgentHeaderProps) {
  return (
    <header className={ui.header}>
      <button className={ui.iconButton} type="button" aria-label="Toggle history" onClick={onToggleHistory}>
        <Menu size={20} strokeWidth={2.25} />
      </button>
      <div className={ui.titleBlock}>
        <span className={ui.kicker}>OpenAPI-aware</span>
        <strong className={ui.title}>{title}</strong>
      </div>
      <button className={ui.iconButton} type="button" aria-label="New chat" onClick={onNewChat}>
        <PenLine size={19} strokeWidth={2.25} />
      </button>
      {canClose ? (
        <button
          className={ui.iconButton}
          type="button"
          aria-label="Close sidebar"
          onClick={() => window.parent?.postMessage({ type: "foa-widget-close" }, "*")}
        >
          <X size={20} strokeWidth={2.25} />
        </button>
      ) : null}
    </header>
  );
}
