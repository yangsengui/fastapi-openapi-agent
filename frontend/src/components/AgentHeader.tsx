import { Menu, PenLine, X } from "lucide-react";

import { ui } from "../app/styles";
import type { UiCopy } from "../app/i18n";

type AgentHeaderProps = {
  title: string;
  copy: UiCopy;
  canClose: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
};

export function AgentHeader({ title, copy, canClose, onToggleHistory, onNewChat }: AgentHeaderProps) {
  return (
    <header className={ui.header}>
      <button className={ui.iconButton} type="button" aria-label={copy.toggleHistory} onClick={onToggleHistory}>
        <Menu size={20} strokeWidth={2.25} />
      </button>
      <div className={ui.titleBlock}>
        <strong className={ui.title}>{title}</strong>
      </div>
      <button className={ui.iconButton} type="button" aria-label={copy.newChat} onClick={onNewChat}>
        <PenLine size={19} strokeWidth={2.25} />
      </button>
      {canClose ? (
        <button
          className={ui.iconButton}
          type="button"
          aria-label={copy.closeSidebar}
          onClick={() => window.parent?.postMessage({ type: "foa-widget-close" }, "*")}
        >
          <X size={20} strokeWidth={2.25} />
        </button>
      ) : null}
    </header>
  );
}
