from __future__ import annotations

import inspect
import json
import mimetypes
import os
from dataclasses import dataclass
from html import escape
from importlib import resources
from pathlib import PurePosixPath
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional, Sequence, Union

import httpx
from django.core.asgi import get_asgi_application
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from ninja import NinjaAPI, Router

from .events import event_payload
from .i18n import DEFAULT_DESCRIPTIONS, Language, validate_language
from .responder import AgentRequest, AgentResponse, default_openapi_responder
from .runtime import OpenAPIAgentRuntime as CoreOpenAPIAgentRuntime
from .sdk import OpenAPIAgent

Responder = Callable[
    [AgentRequest, Dict[str, Any]], Union[AgentResponse, Awaitable[AgentResponse]]
]

STATIC_PACKAGE = "openagent.static"

__all__ = [
    "DjangoNinjaOperationInvoker",
    "OpenAPIAgentConfig",
    "OpenAPIAgentRuntime",
    "install_openapi_agent",
]


@dataclass
class OpenAPIAgentConfig:
    """Runtime options for the OpenAgent Django Ninja adapter."""

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
    forward_headers: tuple[str, ...] = (
        "authorization",
        "cookie",
        "x-csrftoken",
    )
    agent: Optional[OpenAPIAgent] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_kwargs: Optional[Dict[str, Any]] = None
    welcome_title: Optional[str] = None
    language: Language = "en"
    openapi_path_prefix: Optional[str] = None
    asgi_app: Optional[Any] = None


class DjangoNinjaOperationInvoker:
    """Execute operations against the host Django application via ASGI."""

    def __init__(
        self,
        app: Optional[Any] = None,
        *,
        base_url: str = "http://localhost",
    ) -> None:
        self.app = app or get_asgi_application()
        self.base_url = base_url

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
            base_url=self.base_url,
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
    """Django Ninja runtime wrapper backed by the framework-neutral core."""

    def __init__(
        self,
        api: NinjaAPI,
        openapi: Dict[str, Any],
        *,
        agent_path: str = "/_agent",
        enable_api_calls: bool = True,
        allow_mutating_api_calls: bool = False,
        request: Optional[HttpRequest] = None,
        forward_headers: Sequence[str] = (
            "authorization",
            "cookie",
            "x-csrftoken",
        ),
        language: Language = "en",
        asgi_app: Optional[Any] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api = api
        self.request = request
        super().__init__(
            openapi,
            invoker=DjangoNinjaOperationInvoker(
                asgi_app,
                base_url=base_url or _request_base_url(request),
            ),
            agent_path=agent_path,
            enable_api_calls=enable_api_calls,
            allow_mutating_api_calls=allow_mutating_api_calls,
            forwarded_headers=_forwarded_request_headers(request, forward_headers),
            language=language,
        )


def install_openapi_agent(
    api: NinjaAPI, config: Optional[OpenAPIAgentConfig] = None, **overrides: Any
) -> Router:
    """Attach OpenAgent routes to an existing Django Ninja API."""

    resolved = _resolve_config(config, overrides)
    resolved.language = validate_language(resolved.language)
    if resolved.agent is not None and resolved.responder is not None:
        raise ValueError("Configure either agent or responder, not both.")

    base_path = _normalize_path(resolved.path)
    router = Router()

    @router.get("", include_in_schema=resolved.include_in_schema)
    @router.get("/", include_in_schema=resolved.include_in_schema)
    def agent_page(request: HttpRequest) -> HttpResponse:
        mounted_path = _mounted_base_path(request)
        return HttpResponse(
            _render_agent_page(resolved, mounted_path),
            content_type="text/html; charset=utf-8",
        )

    @router.get("/sidebar.js", include_in_schema=resolved.include_in_schema)
    def sidebar_script(request: HttpRequest) -> HttpResponse:
        del request
        js = resources.files(STATIC_PACKAGE).joinpath("sidebar.js")
        return HttpResponse(
            js.read_text(encoding="utf-8"),
            content_type="application/javascript; charset=utf-8",
        )

    @router.get("/widget", include_in_schema=resolved.include_in_schema)
    @router.get("/widget/", include_in_schema=resolved.include_in_schema)
    def widget_app(request: HttpRequest) -> HttpResponse:
        html_file = resources.files(STATIC_PACKAGE).joinpath("widget/index.html")
        if not html_file.is_file():
            return JsonResponse(
                {"detail": "Widget SPA is not built. Run npm --prefix frontend run build."},
                status=404,
            )
        mounted_path = _mounted_base_path(request, "/widget")
        html = html_file.read_text(encoding="utf-8")
        html = html.replace('src="./assets/', f'src="{mounted_path}/widget/assets/')
        html = html.replace('href="./assets/', f'href="{mounted_path}/widget/assets/')
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    @router.get(
        "/widget/assets/{path:asset_path}",
        include_in_schema=resolved.include_in_schema,
    )
    def widget_asset(request: HttpRequest, asset_path: str) -> HttpResponse:
        del request
        relative_path = PurePosixPath(asset_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            return JsonResponse({"detail": "Widget asset not found."}, status=404)
        root = resources.files(STATIC_PACKAGE).joinpath("widget/assets")
        asset = root.joinpath(*relative_path.parts)
        if not asset.is_file():
            return JsonResponse({"detail": "Widget asset not found."}, status=404)
        media_type = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
        return HttpResponse(asset.read_bytes(), content_type=media_type)

    @router.get("/config", include_in_schema=resolved.include_in_schema)
    def agent_config(request: HttpRequest) -> JsonResponse:
        mounted_path = _mounted_base_path(request, "/config")
        return JsonResponse(
            {
                "title": resolved.title,
                "welcomeTitle": resolved.welcome_title,
                "description": _resolved_description(resolved),
                "language": resolved.language,
                "basePath": mounted_path,
                "openapiPath": (
                    f"{mounted_path}/openapi" if resolved.expose_openapi else None
                ),
                "enableApiCalls": resolved.enable_api_calls,
                "allowMutatingApiCalls": resolved.allow_mutating_api_calls,
            }
        )

    if resolved.expose_openapi:

        @router.get("/openapi", include_in_schema=resolved.include_in_schema)
        def openapi_snapshot(request: HttpRequest) -> JsonResponse:
            del request
            return JsonResponse(_openapi_document(api, resolved.openapi_path_prefix))

    @router.post(
        "/chat",
        response=AgentResponse,
        include_in_schema=resolved.include_in_schema,
    )
    async def chat(request: HttpRequest, payload: AgentRequest) -> AgentResponse:
        openapi = _openapi_document(api, resolved.openapi_path_prefix)
        language = _request_language(payload, resolved.language)
        runtime = OpenAPIAgentRuntime(
            api,
            openapi,
            agent_path=_mounted_base_path(request, "/chat"),
            enable_api_calls=resolved.enable_api_calls,
            allow_mutating_api_calls=resolved.allow_mutating_api_calls,
            request=request,
            forward_headers=resolved.forward_headers,
            language=language,
            asgi_app=resolved.asgi_app,
        )
        if resolved.agent is not None:
            return await resolved.agent.respond(payload, openapi, runtime)
        responder = _resolve_responder(resolved, runtime, language)
        result = responder(payload, openapi)
        if inspect.isawaitable(result):
            result = await result
        return result

    @router.post("/chat/stream", include_in_schema=resolved.include_in_schema)
    async def chat_stream(
        request: HttpRequest, payload: AgentRequest
    ) -> StreamingHttpResponse:
        openapi = _openapi_document(api, resolved.openapi_path_prefix)
        language = _request_language(payload, resolved.language)
        runtime = OpenAPIAgentRuntime(
            api,
            openapi,
            agent_path=_mounted_base_path(request, "/chat/stream"),
            enable_api_calls=resolved.enable_api_calls,
            allow_mutating_api_calls=resolved.allow_mutating_api_calls,
            request=request,
            forward_headers=resolved.forward_headers,
            language=language,
            asgi_app=resolved.asgi_app,
        )

        async def events() -> AsyncIterator[str]:
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
                    language=language,
                ):
                    yield _sse(event)
                yield "data: [DONE]\n\n"
                return

            responder = _resolve_responder(resolved, runtime, language)
            result = responder(payload, openapi)
            if inspect.isawaitable(result):
                result = await result
            result_payload = _model_dump(result)
            yield _sse({"type": "start", "messageId": "assistant_fallback"})
            yield _sse({"type": "text-start", "id": "text-1"})
            yield _sse(
                {"type": "text-delta", "id": "text-1", "delta": result.answer}
            )
            yield _sse({"type": "text-end", "id": "text-1"})
            yield _sse({"type": "finish", "response": result_payload})
            yield "data: [DONE]\n\n"

        return StreamingHttpResponse(
            events(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    api.add_router(base_path, router)
    return router


def _openapi_document(api: NinjaAPI, path_prefix: Optional[str]) -> Dict[str, Any]:
    schema = api.get_openapi_schema(path_prefix=path_prefix)
    return _model_dump(schema)


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


def _mounted_base_path(request: HttpRequest, suffix: str = "") -> str:
    path = request.path_info.rstrip("/")
    normalized_suffix = suffix.rstrip("/")
    if normalized_suffix and path.endswith(normalized_suffix):
        path = path[: -len(normalized_suffix)].rstrip("/")
    return path or "/"


def _request_base_url(request: Optional[HttpRequest]) -> str:
    if request is None:
        return "http://localhost"
    return request.build_absolute_uri("/").rstrip("/")


def _resolve_responder(
    config: OpenAPIAgentConfig,
    runtime: OpenAPIAgentRuntime,
    language: Language,
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
            language=language,
        )
    return lambda request, openapi: default_openapi_responder(
        request, openapi, language
    )


def _request_language(request: AgentRequest, default: Language) -> Language:
    requested = request.context.get("language")
    if requested in {"en", "zh"}:
        return requested
    return default


def _resolved_description(config: OpenAPIAgentConfig) -> str:
    if config.description == DEFAULT_DESCRIPTIONS["en"]:
        return DEFAULT_DESCRIPTIONS[config.language]
    return config.description


def _resolve_llm_model(config: OpenAPIAgentConfig) -> Optional[str]:
    if not config.auto_llm:
        return None
    return config.llm_model or os.getenv("OPENAGENT_MODEL") or None


def _forwarded_request_headers(
    request: Optional[HttpRequest], forward_headers: Sequence[str]
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
    if hasattr(value, "model_dump_json"):
        return json.loads(value.model_dump_json(by_alias=True, exclude_none=True))
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True, exclude_none=True)
    elif hasattr(value, "dict"):
        value = value.dict(by_alias=True, exclude_none=True)
    else:
        value = dict(value)
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _render_agent_page(config: OpenAPIAgentConfig, base_path: str) -> str:
    title = escape(config.title)
    description = escape(_resolved_description(config))
    client_config = json.dumps(
        {
            "baseUrl": base_path,
            "title": config.title,
            "welcomeTitle": config.welcome_title,
            "description": _resolved_description(config),
            "language": config.language,
            "container": "#openagent-root",
            "open": config.open_by_default,
            "theme": config.theme,
            "width": 560,
            "minWidth": 420,
            "maxWidth": 920,
        }
    )
    return f"""<!doctype html>
<html lang=\"{config.language}\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title}</title>
    <style>
      * {{ box-sizing: border-box; }}
      html, body {{ height: 100%; }}
      body {{ margin: 0; color: #2b2824; background: #fbfaf7; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
      main {{ height: 100%; display: grid; grid-template-columns: minmax(280px, 1fr) minmax(420px, 620px); gap: 40px; align-items: center; }}
      .intro {{ padding: 48px 0 48px 56px; }}
      h1 {{ margin: 0 0 14px; font-size: clamp(40px, 6vw, 64px); font-weight: 500; letter-spacing: -0.03em; }}
      p {{ margin: 0; color: #6b6862; font-size: 17px; line-height: 1.7; }}
      #openagent-root {{ height: 100vh; min-height: 0; }}
      @media (max-width: 900px) {{
        main {{ grid-template-columns: 1fr; gap: 20px; padding: 24px 18px; }}
        .intro {{ padding: 0; }}
        #openagent-root {{ height: min(720px, calc(100vh - 180px)); min-height: 520px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class=\"intro\"><h1>{title}</h1><p>{description}</p></section>
      <section id=\"openagent-root\" aria-label=\"OpenAPI agent\"></section>
    </main>
    <script>window.OpenAgent = {client_config};</script>
    <script src=\"{base_path}/sidebar.js\"></script>
  </body>
</html>"""
