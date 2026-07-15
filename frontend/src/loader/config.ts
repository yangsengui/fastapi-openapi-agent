import type { LoaderConfig } from "./types";

export function resolveBaseUrl(config: LoaderConfig): string {
  const script = document.currentScript as HTMLScriptElement | null;
  const fromScript = script?.src ? script.src.replace(/\/sidebar\.js(?:\?.*)?$/, "") : "";
  return String(config.baseUrl || fromScript || "/_agent").replace(/\/$/, "");
}

export function resolveContainer(value: LoaderConfig["container"]): HTMLElement | null {
  if (!value) return document.querySelector<HTMLElement>("#openagent-root");
  if (typeof value === "string") return document.querySelector<HTMLElement>(value);
  return value;
}

export function frameSrc(baseUrl: string, config: LoaderConfig, embedded: boolean): string {
  const widgetConfig = {
    baseUrl,
    title: config.title || "OpenAgent",
    description: config.description || "Ask about this service's OpenAPI schema.",
    theme: config.theme || "default",
    mode: embedded ? "embedded" : "floating",
    requestBridge: typeof config.request === "function",
    parentOrigin: window.location.origin,
  };
  return `${baseUrl}/widget/?config=${encodeURIComponent(JSON.stringify(widgetConfig))}`;
}
