import asyncio

import httpx
from django.conf import settings

if not settings.configured:
    settings.configure(
        ALLOWED_HOSTS=["testserver"],
        DEBUG=True,
        MIDDLEWARE=[],
        ROOT_URLCONF=__name__,
        SECRET_KEY="test-secret",
    )

import django

django.setup()

from django.core.asgi import get_asgi_application
from django.urls import path
from ninja import NinjaAPI

from openagent import AgentBackend, AgentContext, AgentResponse, OpenAPIAgent
from openagent.django_ninja import install_openapi_agent


class ProjectsBackend(AgentBackend):
    async def respond(self, context: AgentContext) -> AgentResponse:
        await context.run_tool("operation_get", {"operationId": "list_projects"})
        result = await context.run_tool(
            "operation_request", {"operationId": "list_projects"}
        )
        return AgentResponse(
            answer=(
                f"Found {len(result['data'])} project as "
                f"{result['data'][0]['authorization']}."
            ),
            sources=["GET /api/projects"],
        )


api = NinjaAPI(title="Django Ninja Test API", urls_namespace="django-ninja-test")


@api.get("/projects", operation_id="list_projects", summary="List projects")
def list_projects(request):
    return [
        {
            "name": "OpenAgent",
            "authorization": request.headers.get("authorization"),
        }
    ]


install_openapi_agent(
    api,
    agent=OpenAPIAgent(ProjectsBackend()),
    auto_llm=False,
    language="zh",
)

urlpatterns = [path("api/", api.urls)]


def request_app(
    requests: list[tuple[str, str, dict[str, object]]],
) -> list[httpx.Response]:
    async def send() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=get_asgi_application())
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return [
                await client.request(method, request_path, **kwargs)
                for method, request_path, kwargs in requests
            ]

    return asyncio.run(send())


def test_django_ninja_agent_serves_ui_config_and_schema() -> None:
    page, config, schema = request_app(
        [
            ("GET", "/api/_agent/", {}),
            ("GET", "/api/_agent/config", {}),
            ("GET", "/api/_agent/openapi", {}),
        ]
    )

    assert page.status_code == 200
    assert '<html lang="zh">' in page.text
    assert 'src="/api/_agent/sidebar.js"' in page.text
    assert config.json()["basePath"] == "/api/_agent"
    assert config.json()["openapiPath"] == "/api/_agent/openapi"
    assert config.json()["language"] == "zh"
    assert "/api/projects" in schema.json()["paths"]
    assert "/api/_agent/chat" not in schema.json()["paths"]


def test_django_ninja_agent_executes_host_api_and_streams() -> None:
    response, stream = request_app(
        [
            (
                "POST",
                "/api/_agent/chat",
                {
                    "json": {"message": "list projects"},
                    "headers": {"Authorization": "Bearer test-token"},
                },
            ),
            (
                "POST",
                "/api/_agent/chat/stream",
                {
                    "json": {"message": "list projects"},
                    "headers": {"Authorization": "Bearer test-token"},
                },
            ),
        ]
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Found 1 project as Bearer test-token."
    assert response.json()["sources"] == ["GET /api/projects"]
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert '"type": "start"' in stream.text
    assert '"delta": "Found 1 project as Bearer test-token."' in stream.text
    assert stream.text.endswith("data: [DONE]\n\n")


def test_django_ninja_widget_uses_mounted_asset_path() -> None:
    widget = request_app([("GET", "/api/_agent/widget/", {})])[0]

    assert widget.status_code == 200
    assert "/api/_agent/widget/assets/" in widget.text
