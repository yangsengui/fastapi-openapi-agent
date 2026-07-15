const styleId = "foa-loader-styles";

export function injectStyles(): void {
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
