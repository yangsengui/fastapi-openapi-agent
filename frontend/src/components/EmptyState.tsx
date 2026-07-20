import { ui } from "../app/styles";
import { greeting } from "../lib/utils";
import type { UiCopy } from "../app/i18n";
import type { Language } from "../types";

type EmptyStateProps = {
  title: string;
  welcomeTitle: string | null;
  description: string;
  copy: UiCopy;
  language: Language;
  onSelectPrompt: (prompt: string) => void;
};

export function EmptyState({ title, welcomeTitle, description, copy, language, onSelectPrompt }: EmptyStateProps) {
  return (
    <section className={ui.hero}>
      <h1 className={ui.heroTitle}>{welcomeTitle || greeting(title, language)}</h1>
      <p className={ui.heroDescription}>{description}</p>
      <div className={ui.prompts}>
        {copy.prompts.map((prompt) => (
          <button key={prompt} className={ui.promptButton} type="button" onClick={() => onSelectPrompt(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
