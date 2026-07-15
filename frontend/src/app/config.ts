import type { WidgetConfig } from "../types";

const defaults: WidgetConfig = {
  baseUrl: "/_agent",
  title: "OpenAPI Agent",
  description: "Ask about this service's OpenAPI schema.",
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
    return {
      baseUrl: String(parsed.baseUrl || defaults.baseUrl).replace(/\/$/, ""),
      title: parsed.title || defaults.title,
      description: parsed.description || defaults.description,
      theme: parsed.theme === "ocean" ? "ocean" : "default",
      mode: parsed.mode === "embedded" ? "embedded" : "floating",
      requestBridge: parsed.requestBridge === true,
      parentOrigin: typeof parsed.parentOrigin === "string" ? parsed.parentOrigin : null,
    };
  } catch {
    return defaults;
  }
}
