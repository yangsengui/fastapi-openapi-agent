(function() {
	//#region src/sidebar-loader.ts
	var styleId = "foa-loader-styles";
	var defaultPanelWidth = 560;
	var defaultMinPanelWidth = 420;
	var defaultMaxPanelWidth = 920;
	function resolveBaseUrl(config) {
		const script = document.currentScript;
		const fromScript = script?.src ? script.src.replace(/\/sidebar\.js(?:\?.*)?$/, "") : "";
		return String(config.baseUrl || fromScript || "/_agent").replace(/\/$/, "");
	}
	function resolveContainer(value) {
		if (!value) return document.querySelector("#openagent-root");
		if (typeof value === "string") return document.querySelector(value);
		return value;
	}
	function numericConfig(value, fallback) {
		return typeof value === "number" && Number.isFinite(value) ? value : fallback;
	}
	function clamp(value, min, max) {
		return Math.min(Math.max(value, min), max);
	}
	function setupResize(element, config, storageKey) {
		const minWidth = Math.max(280, numericConfig(config.minWidth, defaultMinPanelWidth));
		const maxWidth = Math.max(minWidth, numericConfig(config.maxWidth, defaultMaxPanelWidth));
		let currentWidth = numericConfig(config.width, defaultPanelWidth);
		try {
			const stored = localStorage.getItem(storageKey);
			const parsed = stored === null ? NaN : Number(stored);
			if (Number.isFinite(parsed)) currentWidth = parsed;
		} catch {}
		const applyWidth = (width) => {
			const viewportMax = Math.min(maxWidth, Math.max(minWidth, window.innerWidth - 24));
			const nextWidth = clamp(Math.round(width), minWidth, viewportMax);
			element.style.setProperty("--foa-loader-width", `${nextWidth}px`);
			return nextWidth;
		};
		const persistWidth = () => {
			try {
				localStorage.setItem(storageKey, String(currentWidth));
			} catch {}
		};
		currentWidth = applyWidth(currentWidth);
		const handle = document.createElement("button");
		handle.type = "button";
		handle.className = "foa-loader-resize-handle";
		handle.setAttribute("aria-label", "Resize assistant sidebar");
		handle.setAttribute("aria-orientation", "vertical");
		handle.setAttribute("role", "separator");
		handle.setAttribute("title", "Drag to resize");
		let drag = null;
		let overlay = null;
		const removeOverlay = () => {
			overlay?.remove();
			overlay = null;
		};
		const moveDrag = (event) => {
			if (!drag || event.pointerId !== drag.pointerId) return;
			currentWidth = applyWidth(drag.rightEdge - event.clientX);
		};
		const finishDrag = (event) => {
			if (!drag || event.pointerId !== drag.pointerId) return;
			try {
				handle.releasePointerCapture(event.pointerId);
			} catch {}
			drag = null;
			removeOverlay();
			document.documentElement.classList.remove("foa-loader-resizing");
			persistWidth();
		};
		handle.addEventListener("pointerdown", (event) => {
			if (window.matchMedia("(max-width: 640px)").matches) return;
			drag = {
				pointerId: event.pointerId,
				rightEdge: element.getBoundingClientRect().right
			};
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
	function injectStyles() {
		if (document.getElementById(styleId)) return;
		const style = document.createElement("style");
		style.id = styleId;
		style.textContent = `
    .foa-loader-launcher{position:fixed;right:22px;bottom:22px;z-index:2147483000;display:flex;gap:8px;align-items:center;border:0;border-radius:999px;padding:10px 16px 10px 10px;background:linear-gradient(to top right,#eabf9f,#d8a883);color:#2c1d11;box-shadow:0 16px 40px rgba(15,23,42,.22);cursor:pointer;font:600 13px/1.2 Inter,system-ui,-apple-system,Segoe UI,sans-serif}
    .foa-loader-orb{display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:rgba(0,0,0,.12);font-weight:800;font-size:12px;letter-spacing:.02em}
    .foa-loader-launcher[data-theme="ocean"]{background:linear-gradient(to top right,#14b8a6,#0f766e);color:#ecfeff}
    .foa-loader-hidden{display:none}
    .foa-loader-frame-wrap{position:fixed;top:0;right:0;bottom:0;width:min(var(--foa-loader-width,560px),100vw);height:100dvh;z-index:2147483001;transform:translateX(105%);transition:transform .22s cubic-bezier(.22,1,.36,1);pointer-events:none;background:transparent;overflow:visible;will-change:transform}
    .foa-loader-frame-wrap.foa-loader-open{transform:translateX(0);pointer-events:auto}
    .foa-loader-frame{width:100%;height:100%;border:0;background:transparent}
    .foa-loader-inline{position:relative;width:var(--foa-loader-width,560px);height:100dvh;min-height:0;max-width:100vw;overflow:visible}
    .foa-loader-inline .foa-loader-frame{min-height:0;border-radius:0}
    .foa-loader-resize-handle{position:absolute;top:0;bottom:0;left:-12px;z-index:2147483002;width:24px;padding:0;border:0;background:transparent;cursor:ew-resize;touch-action:none}
    .foa-loader-resize-handle::after{content:"";position:absolute;top:50%;left:11px;width:3px;height:64px;border-radius:999px;background:rgba(100,116,139,.42);opacity:.75;transform:translateY(-50%);transition:opacity .15s ease,background .15s ease,width .15s ease}
    .foa-loader-resize-handle:hover::after,.foa-loader-resize-handle:focus-visible::after{width:4px;background:rgba(200,117,85,.95);opacity:1}
    .foa-loader-resize-overlay{position:fixed;inset:0;z-index:2147483003;cursor:ew-resize;background:transparent;touch-action:none}
    .foa-loader-resize-handle:focus-visible{outline:2px solid rgba(200,117,85,.45);outline-offset:2px}
    html.foa-loader-resizing,html.foa-loader-resizing *{cursor:ew-resize!important;user-select:none!important}
    @media(max-width:640px){.foa-loader-launcher{right:14px;bottom:14px}.foa-loader-frame-wrap{width:100vw!important}.foa-loader-inline{width:100%;height:100dvh}.foa-loader-resize-handle{display:none}}
  `;
		document.head.appendChild(style);
	}
	function frameSrc(baseUrl, config, embedded) {
		const widgetConfig = {
			baseUrl,
			title: config.title || "OpenAgent",
			description: config.description || "Ask about this service's OpenAPI schema.",
			theme: config.theme || "default",
			mode: embedded ? "embedded" : "floating"
		};
		return `${baseUrl}/widget/?config=${encodeURIComponent(JSON.stringify(widgetConfig))}`;
	}
	function boot() {
		if (window.__OpenAgentLoaded) return;
		window.__OpenAgentLoaded = true;
		const config = window.OpenAgent || {};
		const baseUrl = resolveBaseUrl(config);
		const target = resolveContainer(config.container);
		const embedded = Boolean(target);
		const storageKey = `foa:open:${baseUrl}`;
		const src = frameSrc(baseUrl, config, embedded);
		injectStyles();
		if (embedded && target) {
			target.classList.add("foa-loader-inline");
			const iframe = document.createElement("iframe");
			iframe.className = "foa-loader-frame";
			iframe.title = config.title || "OpenAgent";
			iframe.src = src;
			iframe.allow = "clipboard-read; clipboard-write";
			target.appendChild(iframe);
			setupResize(target, config, `foa:width:v2:${baseUrl}:embedded`);
			return;
		}
		const launcher = document.createElement("button");
		launcher.type = "button";
		launcher.className = "foa-loader-launcher";
		launcher.dataset.theme = config.theme || "default";
		launcher.innerHTML = "<span class=\"foa-loader-orb\">AI</span><span>API Agent</span>";
		document.body.appendChild(launcher);
		const wrapper = document.createElement("div");
		wrapper.className = "foa-loader-frame-wrap";
		const iframe = document.createElement("iframe");
		iframe.className = "foa-loader-frame";
		iframe.title = config.title || "OpenAgent";
		iframe.src = src;
		iframe.allow = "clipboard-read; clipboard-write";
		wrapper.appendChild(iframe);
		setupResize(wrapper, config, `foa:width:v2:${baseUrl}:floating`);
		document.body.appendChild(wrapper);
		const setOpen = (open) => {
			wrapper.classList.toggle("foa-loader-open", open);
			launcher.classList.toggle("foa-loader-hidden", open);
			try {
				sessionStorage.setItem(storageKey, open ? "true" : "false");
			} catch {}
		};
		launcher.addEventListener("click", () => setOpen(true));
		window.addEventListener("message", (event) => {
			if (event.source !== iframe.contentWindow || !event.data || typeof event.data !== "object") return;
			if (event.data.type === "foa-widget-close") setOpen(false);
		});
		document.addEventListener("keydown", (event) => {
			const targetEl = event.target;
			if (targetEl && [
				"INPUT",
				"TEXTAREA",
				"SELECT"
			].includes(targetEl.tagName) || event.defaultPrevented) return;
			if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "e") {
				event.preventDefault();
				setOpen(!wrapper.classList.contains("foa-loader-open"));
			}
		});
		let initiallyOpen = config.open === true;
		try {
			initiallyOpen = sessionStorage.getItem(storageKey) === "true" || initiallyOpen;
		} catch {}
		setOpen(initiallyOpen);
	}
	boot();
	//#endregion
})();
