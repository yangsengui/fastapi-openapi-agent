import { LoaderCircle, SendHorizontal } from "lucide-react";
import { useEffect } from "react";
import type { FormEvent, RefObject } from "react";

import { ui } from "../app/styles";

type ComposerProps = {
  draft: string;
  busy: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onDraftChange: (value: string) => void;
  onSubmit: (event?: FormEvent) => void;
};

export function Composer({ draft, busy, textareaRef, onDraftChange, onSubmit }: ComposerProps) {
  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 156)}px`;
  }, [draft, textareaRef]);

  return (
    <form className={ui.composer} onSubmit={onSubmit}>
      <div className={ui.composerShell}>
        <textarea
          ref={textareaRef}
          className={ui.textarea}
          value={draft}
          rows={1}
          placeholder="Ask about the API, or ask the agent to call an endpoint..."
          aria-label="Message"
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <div className={ui.composerFooter}>
          <span className={ui.composerHint}>Enter to send · Shift Enter for newline</span>
          <button className={ui.sendButton} type="submit" disabled={busy || !draft.trim()} aria-label={busy ? "Sending" : "Send message"}>
            {busy ? <LoaderCircle className="animate-spin" size={18} strokeWidth={2.4} /> : <SendHorizontal size={18} strokeWidth={2.4} />}
          </button>
        </div>
      </div>
    </form>
  );
}
