from __future__ import annotations

import inspect
import json
import mimetypes
import os
from dataclasses import dataclass
from html import escape
from importlib import resources
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence, Union

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from .events import event_payload
from .responder import AgentRequest, AgentResponse, default_openapi_responder
from .runtime import OpenAPIAgentRuntime as CoreOpenAPIAgentRuntime
from .sdk import OpenAPIAgent

Responder = Callable[
    [AgentRequest, Dict[str, Any]], Union[AgentResponse, Awaitable[AgentResponse]]
]

STATIC_PACKAGE = "openagent.static"


@dataclass
class OpenAPIAgentConfig:
    """Runtime options for the OpenAgent FastAPI adapter."""

    path: str = "/_agent"
    title: str = "OpenAgent"
    description: str = "Ask questions about this service's OpenAPI schema."
    responder: Optional[Responder] = None
    include_in_schema: bool = False
    expose_openapi: bool = True
    theme: str = "default"
    open_by_default: bool = True
    enable_api_calls: bool = True
    allow_mutating_api_calls: bool = False
    auto_llm: bool = True
    forward_headers: tuple[str, ...] = ("authorization", "cookie")
    agent: Optional[OpenAPIAgent] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_kwargs: Optional[Dict[str, Any]] = None


class FastAPIOperationInvoker:
    """Execute operations against the host FastAPI app in-process via ASGI."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Dict[str, Any],
        headers: Dict[str, str],
        body: Any,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://openagent.local",
            timeout=30,
            follow_redirects=False,
        ) as client:
            return await client.request(
                method,
                path,
                params=query,
                headers=headers,
                json=body if body is not None else None,
            )


class OpenAPIAgentRuntime(CoreOpenAPIAgentRuntime):
    """FastAPI runtime wrapper backed by the framework-neutral OpenAgent core."""

    def __init__(
        self,
        app: FastAPI,
        openapi: Dict[str, Any],
        *,
        agent_path: str = "/_agent",
        enable_api_calls: bool = True,
        allow_mutating_api_calls: bool = False,
        request: Optional[Request] = None,
        forward_headers: Sequence[str] = ("authorization", "cookie"),
    ) -> None:
        self.app = app
        self.request = request
        super().__init__(
            openapi,
            invoker=FastAPIOperationInvoker(app),
            agent_path=agent_path,
            enable_api_calls=enable_api_calls,
            allow_mutating_api_calls=allow_mutating_api_calls,
            forwarded_headers=_forwarded_request_headers(request, forward_headers),
        )


def install_openapi_agent(
    app: FastAPI, config: Optional[OpenAPIAgentConfig] = None, **overrides: Any
) -> APIRouter:
    """Attach OpenAgent routes to an existing FastAPI application."""

    resolved = _resolve_config(config, overrides)
    if resolved.agent is not None and resolved.responder is not None:
        raise ValueError("Configure either agent or responder, not both.")
    base_path = _normalize_path(resolved.path)

    router = APIRouter(prefix=base_path, include_in_schema=resolved.include_in_schema)

    @router.get("/", response_class=HTMLResponse)
    async def agent_page(_: Request) -> HTMLResponse:
        return HTMLResponse(_render_agent_page(resolved, base_path))

    @router.get("/sidebar.js")
    async def sidebar_script() -> Response:
        js = resources.files(STATIC_PACKAGE).joinpath("sidebar.js")
        return Response(js.read_text(encoding="utf-8"), media_type="application/javascript")

    @router.get("/widget", response_class=HTMLResponse)
    @router.get("/widget/", response_class=HTMLResponse)
    async def widget_app(_: Request) -> HTMLResponse:
        html_file = resources.files(STATIC_PACKAGE).joinpath("widget/index.html")
        if not html_file.is_file():
            raise HTTPException(status_code=404, detail="Widget SPA is not built. Run npm --prefix frontend run build.")
        html = html_file.read_text(encoding="utf-8")
        html = html.replace('src="./assets/', f'src="{base_path}/widget/assets/')
        html = html.replace('href="./assets/', f'href="{base_path}/widget/assets/')
        return HTMLResponse(html)

    @router.get("/widget/assets/{asset_path:path}")
    async def widget_asset(asset_path: str) -> Response:
        root = resources.files(STATIC_PACKAGE).joinpath("widget/assets")
        asset = root.joinpath(asset_path)
        if not asset.is_file():
            raise HTTPException(status_code=404, detail="Widget asset not found.")
        media_type = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
        return Response(asset.read_bytes(), media_type=media_type)

    @router.get("/config")
    async def agent_config() -> Dict[str, Any]:
        return {
            "title": resolved.title,
            "description": resolved.description,
            "basePath": base_path,
            "openapiPath": f"{base_path}/openapi" if resolved.expose_openapi else None,
            "enableApiCalls": resolved.enable_api_calls,
            "allowMutatingApiCalls": resolved.allow_mutating_api_calls,
        }

    if resolved.expose_openapi:

        @router.get("/openapi")
        async def openapi_snapshot() -> JSONResponse:
            return JSONResponse(app.openapi())

    @router.post("/chat", response_model=AgentResponse)
    async def chat(payload: AgentRequest, request: Request) -> AgentResponse:
        openapi = app.openapi()
        runtime = OpenAPIAgentRuntime(
            app,
            openapi,
            agent_path=base_path,
            enable_api_calls=resolved.enable_api_calls,
            allow_mutating_api_calls=resolved.allow_mutating_api_calls,
            request=request,
            forward_headers=resolved.forward_headers,
        )
        if resolved.agent is not None:
            return await resolved.agent.respond(payload, openapi, runtime)
        responder = _resolve_responder(resolved, runtime)
        result = responder(payload, openapi)
        if inspect.isawaitable(result):
            result = await result
        return result

    @router.post("/chat/stream")
    async def chat_stream(payload: AgentRequest, request: Request) -> StreamingResponse:
        openapi = app.openapi()
        runtime = OpenAPIAgentRuntime(
            app,
            openapi,
            agent_path=base_path,
            enable_api_calls=resolved.enable_api_calls,
            allow_mutating_api_calls=resolved.allow_mutating_api_calls,
            request=request,
            forward_headers=resolved.forward_headers,
        )

        async def events():
            if resolved.agent is not None:
                async for event in resolved.agent.stream(payload, openapi, runtime):
                    yield _sse(event_payload(event))
                yield "data: [DONE]\n\n"
                return

            model = _resolve_llm_model(resolved)
            if resolved.responder is None and model:
                from .llm import stream_llm_agent

                async for event in stream_llm_agent(
                    payload,
                    openapi,
                    runtime.run_tool,
                    model=model,
                    api_key=resolved.llm_api_key,
                    base_url=resolved.llm_base_url,
                    model_kwargs=resolved.llm_model_kwargs,
                ):
                    yield _sse(event)
                yield "data: [DONE]\n\n"
                return

            responder = _resolve_responder(resolved, runtime)
            result = responder(payload, openapi)
            if inspect.isawaitable(result):
                result = await result
            result_payload = _model_dump(result)
            yield _sse({"type": "start", "messageId": "assistant_fallback"})
            yield _sse({"type": "text-start", "id": "text-1"})
            yield _sse({"type": "text-delta", "id": "text-1", "delta": result.answer})
            yield _sse({"type": "text-end", "id": "text-1"})
            yield _sse({"type": "finish", "response": result_payload})
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(router)
    return router


def _resolve_config(
    config: Optional[OpenAPIAgentConfig], overrides: Dict[str, Any]
) -> OpenAPIAgentConfig:
    if config is None:
        return OpenAPIAgentConfig(**overrides)
    if not overrides:
        return config
    values = config.__dict__.copy()
    values.update(overrides)
    return OpenAPIAgentConfig(**values)


def _normalize_path(path: str) -> str:
    normalized = "/" + path.strip("/")
    return normalized.rstrip("/") or "/_agent"


def _resolve_responder(
    config: OpenAPIAgentConfig, runtime: OpenAPIAgentRuntime
) -> Responder:
    if config.responder is not None:
        return config.responder
    model = _resolve_llm_model(config)
    if model:
        from .llm import create_llm_responder

        return create_llm_responder(
            model=model,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            model_kwargs=config.llm_model_kwargs,
            tool_runner=runtime.run_tool,
        )
    return default_openapi_responder


def _resolve_llm_model(config: OpenAPIAgentConfig) -> Optional[str]:
    if not config.auto_llm:
        return None
    model = config.llm_model or os.getenv("OPENAGENT_MODEL")
    if model:
        return model
    return None


def _forwarded_request_headers(
    request: Optional[Request], forward_headers: Sequence[str]
) -> Dict[str, str]:
    if request is None:
        return {}
    allowed = {name.lower() for name in forward_headers}
    return {
        name: value
        for name, value in request.headers.items()
        if name.lower() in allowed
    }


def _sse(event: Dict[str, Any]) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"


def _model_dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _render_agent_page(config: OpenAPIAgentConfig, base_path: str) -> str:
    title = escape(config.title)
    description = escape(config.description)
    client_config = json.dumps(
        {
            "baseUrl": base_path,
            "title": config.title,
            "description": config.description,
            "container": "#openagent-root",
            "open": config.open_by_default,
            "theme": config.theme,
            "width": 560,
            "minWidth": 420,
            "maxWidth": 920,
        }
    )
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title}</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
    <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\" />
    <style>
      * {{ box-sizing: border-box; }}
      html {{ height: 100%; }}
      body {{
        margin: 0;
        height: 100%;
        min-height: 100vh;
        overflow: hidden;
        color: #1f2328;
        background: radial-gradient(circle at 15% 5%, #f4ecdf 0%, #fbfaf7 45%, #f3f0e8 100%);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
      }}
      .page {{
        height: 100vh;
        min-height: 0;
        display: grid;
        gap: 40px;
        grid-template-columns: minmax(360px, 1fr) auto;
        align-items: stretch;
        padding: 0;
      }}
      .hero {{ align-self: center; max-width: 520px; padding: 48px 0 48px 56px; }}
      .eyebrow {{ display: inline-flex; align-items: center; gap: 6px; color: #c87555; font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; margin-bottom: 18px; }}
      .eyebrow::before {{ content: \"\"; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}
      h1 {{ font-size: clamp(40px, 6vw, 64px); font-weight: 500; line-height: 1.02; letter-spacing: -0.03em; margin: 0 0 14px; color: #2b2824; }}
      .lead {{ color: #6b6862; font-size: 17px; line-height: 1.7; margin: 0 0 28px; }}
      .snippets {{ display: flex; flex-direction: column; gap: 10px; }}
      .snippet {{ display: flex; gap: 10px; align-items: flex-start; font-size: 14px; color: #4a463f; line-height: 1.55; }}
      .snippet code {{ background: rgba(200,117,85,.12); color: #c87555; border-radius: 7px; padding: 2px 7px; font: 600 13px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; flex-shrink: 0; }}
      #openagent-root {{ align-self: stretch; justify-self: end; height: 100vh; min-height: 0; }}
      @media (max-width: 960px) {{
        body {{ overflow: auto; }}
        .page {{ height: auto; min-height: 100vh; grid-template-columns: 1fr; padding: 28px 18px; gap: 24px; }}
        .hero {{ max-width: none; padding: 0; }}
        #openagent-root {{ justify-self: stretch; width: 100%; height: min(760px, calc(100vh - 56px)); min-height: 560px; }}
      }}
    </style>
  </head>
  <body>
    <main class=\"page\">
      <section class=\"hero\">
        <span class=\"eyebrow\">OpenAgent</span>
        <h1>{title}</h1>
        <p class=\"lead\">{description}</p>
        <div class=\"snippets\">
          <div class=\"snippet\"><code>&lt;script&gt;</code><span>Drop <code>{base_path}/sidebar.js</code> into any page to add a floating assistant.</span></div>
          <div class=\"snippet\"><code>Ctrl + E</code><span>Toggle the floating drawer from anywhere on the page.</span></div>
          <div class=\"snippet\"><code>/_agent</code><span>Conversations, OpenAPI grounding, and LLM tools live on one route prefix.</span></div>
        </div>
      </section>
      <section id=\"openagent-root\" aria-label=\"OpenAPI agent\"></section>
    </main>
    <script>window.OpenAgent = {client_config};</script>
    <script src=\"{base_path}/sidebar.js\"></script>
  </body>
</html>"""
