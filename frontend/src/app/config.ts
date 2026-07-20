import type { WidgetConfig } from "../types";

const defaults: WidgetConfig = {
  baseUrl: "/_agent",
  title: "OpenAPI Agent",
  welcomeTitle: null,
  description: "Ask about this service's OpenAPI schema.",
  language: "en",
  theme: "default",
  mode: "floating",
  requestBridge: false,
  parentOrigin: null,
};

export function readConfig(): WidgetConfig {
  const raw = new URLSearchParams(window.location.search).get("config");
  if (!raw) return defaults;

  try {
    const parsed = JSON.parse(raw) as Partial<WidgetConfig>;
    const language = parsed.language === "zh" ? "zh" : "en";
    return {
      baseUrl: String(parsed.baseUrl || defaults.baseUrl).replace(/\/$/, ""),
      title: parsed.title || defaults.title,
      welcomeTitle: typeof parsed.welcomeTitle === "string" && parsed.welcomeTitle ? parsed.welcomeTitle : null,
      description: parsed.description || (language === "zh" ? "询问有关此服务 OpenAPI 接口的问题。" : defaults.description),
      language,
      theme: parsed.theme === "ocean" ? "ocean" : "default",
      mode: parsed.mode === "embedded" ? "embedded" : "floating",
      requestBridge: parsed.requestBridge === true,
      parentOrigin: typeof parsed.parentOrigin === "string" ? parsed.parentOrigin : null,
    };
  } catch {
    return defaults;
  }
}
