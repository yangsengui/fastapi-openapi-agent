import { Sparkles } from "lucide-react";

import { ui } from "../app/styles";
import { greeting } from "../lib/utils";

const prompts = [
  "请调用接口列出所有 items",
  "搜索创建资源相关接口",
  "调用健康检查接口",
  "解释完整调用链条",
];

type EmptyStateProps = {
  title: string;
  description: string;
  onSelectPrompt: (prompt: string) => void;
};

export function EmptyState({ title, description, onSelectPrompt }: EmptyStateProps) {
  return (
    <section className={ui.hero}>
      <div className={ui.heroEyebrow}>
        <Sparkles size={14} strokeWidth={2.4} /> OpenAPI Agent Runtime
      </div>
      <h1 className={ui.heroTitle}>{greeting(title)}</h1>
      <p className={ui.heroDescription}>{description}</p>
      <div className={ui.prompts}>
        {prompts.map((prompt) => (
          <button key={prompt} className={ui.promptButton} type="button" onClick={() => onSelectPrompt(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
