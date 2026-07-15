import type { LoaderConfig } from "./types";

const defaultPanelWidth = 560;
const defaultMinPanelWidth = 420;
const defaultMaxPanelWidth = 920;

export function setupResize(element: HTMLElement, config: LoaderConfig, storageKey: string): void {
  const minWidth = Math.max(280, numericConfig(config.minWidth, defaultMinPanelWidth));
  const maxWidth = Math.max(minWidth, numericConfig(config.maxWidth, defaultMaxPanelWidth));
  let currentWidth = numericConfig(config.width, defaultPanelWidth);

  try {
    const stored = localStorage.getItem(storageKey);
    const parsed = stored === null ? NaN : Number(stored);
    if (Number.isFinite(parsed)) currentWidth = parsed;
  } catch {
    // Ignore storage failures.
  }

  const applyWidth = (width: number): number => {
    const viewportMax = Math.min(maxWidth, Math.max(minWidth, window.innerWidth - 24));
    const nextWidth = clamp(Math.round(width), minWidth, viewportMax);
    element.style.setProperty("--foa-loader-width", `${nextWidth}px`);
    return nextWidth;
  };

  const persistWidth = (): void => {
    try {
      localStorage.setItem(storageKey, String(currentWidth));
    } catch {
      // Ignore storage failures.
    }
  };

  currentWidth = applyWidth(currentWidth);
  const handle = createResizeHandle();
  let drag: { pointerId: number; rightEdge: number } | null = null;
  let overlay: HTMLDivElement | null = null;

  const removeOverlay = (): void => {
    overlay?.remove();
    overlay = null;
  };
  const moveDrag = (event: PointerEvent): void => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    currentWidth = applyWidth(drag.rightEdge - event.clientX);
  };
  const finishDrag = (event: PointerEvent): void => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    try {
      handle.releasePointerCapture(event.pointerId);
    } catch {
      // Ignore pointer capture failures.
    }
    drag = null;
    removeOverlay();
    document.documentElement.classList.remove("foa-loader-resizing");
    persistWidth();
  };

  handle.addEventListener("pointerdown", (event) => {
    if (window.matchMedia("(max-width: 640px)").matches) return;
    drag = { pointerId: event.pointerId, rightEdge: element.getBoundingClientRect().right };
    handle.setPointerCapture(event.pointerId);
    overlay = document.createElement("div");
    overlay.className = "foa-loader-resize-overlay";
    overlay.addEventListener("pointermove", moveDrag);
    overlay.addEventListener("pointerup", finishDrag);
    overlay.addEventListener("pointercancel", finishDrag);
    document.body.appendChild(overlay);
    document.documentElement.classList.add("foa-loader-resizing");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", moveDrag);
  handle.addEventListener("pointerup", finishDrag);
  handle.addEventListener("pointercancel", finishDrag);
  handle.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const step = event.shiftKey ? 48 : 24;
    currentWidth = applyWidth(currentWidth + (event.key === "ArrowLeft" ? step : -step));
    persistWidth();
  });
  window.addEventListener("resize", () => {
    currentWidth = applyWidth(currentWidth);
  });
  element.appendChild(handle);
}

function createResizeHandle(): HTMLButtonElement {
  const handle = document.createElement("button");
  handle.type = "button";
  handle.className = "foa-loader-resize-handle";
  handle.setAttribute("aria-label", "Resize assistant sidebar");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("role", "separator");
  handle.setAttribute("title", "Drag to resize");
  return handle;
}

function numericConfig(value: number | undefined, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
