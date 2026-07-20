export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function uid(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2).slice(0, 3000);
  } catch {
    return String(value);
  }
}

export function titleFromPrompt(value: string, language: Language = "en"): string {
  return value.trim().slice(0, 42) || getCopy(language).newChatTitle;
}

export function greeting(title: string, language: Language = "en"): string {
  const hour = new Date().getHours();
  const greetings = getCopy(language).greetings;
  const part = hour < 12 ? greetings[0] : hour < 18 ? greetings[1] : greetings[2];
  return language === "zh" ? `${part}，${title}` : `${part}, ${title}`;
}

export function relativeTime(timestamp: number, language: Language = "en"): string {
  const copy = getCopy(language);
  const diff = Date.now() - timestamp;
  if (diff < 60_000) return copy.justNow;
  if (diff < 3_600_000) return copy.minutesAgo(Math.floor(diff / 60_000));
  if (diff < 86_400_000) return copy.hoursAgo(Math.floor(diff / 3_600_000));
  return new Date(timestamp).toLocaleDateString(language === "zh" ? "zh-CN" : "en");
}
import { getCopy } from "../app/i18n";
import type { Language } from "../types";
