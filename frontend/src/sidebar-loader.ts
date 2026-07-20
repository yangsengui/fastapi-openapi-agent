import { frameSrc, resolveBaseUrl, resolveContainer } from "./loader/config";
import { setupWidgetMessages } from "./loader/request-bridge";
import { setupResize } from "./loader/resize";
import { injectStyles } from "./loader/styles";
import type { LoaderConfig } from "./loader/types";

export {};

declare global {
  interface Window {
    OpenAgent?: LoaderConfig;
    __OpenAgentLoaded?: boolean;
  }
}

function createLauncher(config: LoaderConfig): HTMLButtonElement {
  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.className = "foa-loader-launcher";
  launcher.dataset.theme = config.theme || "default";
  launcher.innerHTML = `<span class="foa-loader-orb">AI</span><span>${config.language === "zh" ? "API 助手" : "API Agent"}</span>`;
  launcher.ariaLabel = config.language === "zh" ? "打开 API 助手" : "Open API agent";
  return launcher;
}

function createFrame(config: LoaderConfig, src: string): HTMLIFrameElement {
  const iframe = document.createElement("iframe");
  iframe.className = "foa-loader-frame";
  iframe.title = config.title || "OpenAgent";
  iframe.src = src;
  iframe.allow = "clipboard-read; clipboard-write";
  return iframe;
}

function setupToggleShortcut(isOpen: () => boolean, setOpen: (open: boolean) => void): void {
  document.addEventListener("keydown", (event) => {
    const target = event.target as HTMLElement | null;
    const editable = target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
    if (editable || event.defaultPrevented) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "e") {
      event.preventDefault();
      setOpen(!isOpen());
    }
  });
}

function mountEmbedded(target: HTMLElement, config: LoaderConfig, src: string, baseUrl: string): void {
  target.classList.add("foa-loader-inline");
  const launcher = createLauncher(config);
  const iframe = createFrame(config, src);
  document.body.appendChild(launcher);
  target.appendChild(iframe);
  setupResize(target, config, `foa:width:v2:${baseUrl}:embedded`);

  const setOpen = (open: boolean): void => {
    target.classList.toggle("foa-loader-hidden", !open);
    launcher.classList.toggle("foa-loader-hidden", open);
  };

  launcher.addEventListener("click", () => setOpen(true));
  setupWidgetMessages(iframe, config, src, baseUrl, () => setOpen(false));
  setupToggleShortcut(() => !target.classList.contains("foa-loader-hidden"), setOpen);
  setOpen(true);
}

function mountFloating(config: LoaderConfig, src: string, baseUrl: string): void {
  const storageKey = `foa:open:${baseUrl}`;
  const launcher = createLauncher(config);
  const wrapper = document.createElement("div");
  const iframe = createFrame(config, src);
  wrapper.className = "foa-loader-frame-wrap";
  wrapper.appendChild(iframe);
  document.body.append(launcher, wrapper);
  setupResize(wrapper, config, `foa:width:v2:${baseUrl}:floating`);

  const setOpen = (open: boolean): void => {
    wrapper.classList.toggle("foa-loader-open", open);
    launcher.classList.toggle("foa-loader-hidden", open);
    try {
      sessionStorage.setItem(storageKey, open ? "true" : "false");
    } catch {
      // Ignore storage failures.
    }
  };

  launcher.addEventListener("click", () => setOpen(true));
  setupWidgetMessages(iframe, config, src, baseUrl, () => setOpen(false));
  setupToggleShortcut(() => wrapper.classList.contains("foa-loader-open"), setOpen);

  let initiallyOpen = config.open === true;
  try {
    initiallyOpen = sessionStorage.getItem(storageKey) === "true" || initiallyOpen;
  } catch {
    // Ignore storage failures.
  }
  setOpen(initiallyOpen);
}

function boot(): void {
  if (window.__OpenAgentLoaded) return;
  window.__OpenAgentLoaded = true;

  const config = window.OpenAgent || {};
  const baseUrl = resolveBaseUrl(config);
  const target = resolveContainer(config.container);
  const src = frameSrc(baseUrl, config, Boolean(target));

  injectStyles();
  if (target) {
    mountEmbedded(target, config, src, baseUrl);
    return;
  }
  mountFloating(config, src, baseUrl);
}

boot();
