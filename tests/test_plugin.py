import asyncio
import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from openagent import AgentRequest, OpenAPIAgentRuntime as CoreOpenAPIAgentRuntime
from openagent.deepseek import create_deepseek_responder, stream_deepseek_agent
from openagent.fastapi import (
    OpenAPIAgentRuntime as FastAPIRuntime,
    install_openapi_agent,
)


class UserCreate(BaseModel):
    email: str


def build_app() -> FastAPI:
    app = FastAPI(title="Test API")

    @app.get("/users", tags=["users"], summary="List users")
    def list_users() -> list[dict[str, str]]:
        return [{"email": "demo@example.com"}]

    @app.post("/users", tags=["users"], summary="Create user")
    def create_user(payload: UserCreate) -> dict[str, str]:
        return payload.dict()

    install_openapi_agent(app, auto_deepseek=False)
    return app


def test_agent_serves_page_and_sidebar() -> None:
    client = TestClient(build_app())

    page = client.get("/_agent/")
    sidebar = client.get("/_agent/sidebar.js")

    assert page.status_code == 200
    assert "OpenAgent" in page.text
    assert sidebar.status_code == 200
    assert "foa-loader-frame" in sidebar.text
    assert "/widget/" in sidebar.text


def test_agent_serves_widget_spa() -> None:
    client = TestClient(build_app())

    widget = client.get("/_agent/widget/")

    assert widget.status_code == 200
    assert "OpenAgent" in widget.text
    assert "/_agent/widget/assets/" in widget.text

def test_core_runtime_searches_openapi_without_fastapi_adapter() -> None:
    runtime = CoreOpenAPIAgentRuntime(build_app().openapi(), enable_api_calls=False)

    result = runtime.operation_search({"query": "create user"})

    assert result["ok"] is True
    assert result["data"]["operations"][0]["path"] == "/users"


def test_agent_exposes_host_openapi_schema() -> None:
    client = TestClient(build_app())

    response = client.get("/_agent/openapi")

    assert response.status_code == 200
    assert "/users" in response.json()["paths"]
    assert "/_agent/chat" not in response.json()["paths"]


def test_agent_chat_returns_matching_operations() -> None:
    client = TestClient(build_app())

    response = client.post("/_agent/chat", json={"message": "How do I create a user?"})

    assert response.status_code == 200
    body = response.json()
    assert "POST /users" in body["answer"]
    assert body["operations"][0]["path"] == "/users"


def test_agent_stream_endpoint_falls_back_to_responder() -> None:
    client = TestClient(build_app())

    response = client.post("/_agent/chat/stream", json={"message": "How do I create a user?"})

    assert response.status_code == 200
    assert "text-delta" in response.text
    assert "finish" in response.text
    assert "POST /users" in response.text


def test_deepseek_responder_calls_chat_completions() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Use POST /users to create a user."}}]},
        )

    responder = create_deepseek_responder(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert "UserCreate" in captured["payload"]["messages"][-1]["content"]
    assert "POST /users" in response.answer
    assert response.operations[0].path == "/users"


def test_deepseek_responder_falls_back_on_api_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    responder = create_deepseek_responder(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert "DeepSeek request failed with HTTP 401" in response.answer
    assert "POST /users" in response.answer


def test_runtime_can_execute_readonly_host_api() -> None:
    app = build_app()
    runtime = FastAPIRuntime(app, app.openapi(), agent_path="/_agent")

    result = asyncio.run(
        runtime.run_tool("operation_request", {"operation": "list_users_users_get"})
    )

    assert result["ok"] is True
    assert result["method"] == "GET"
    assert result["status"] == 200
    assert result["data"] == [{"email": "demo@example.com"}]


def test_deepseek_responder_runs_tool_call_loop() -> None:
    calls = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls["count"] += 1
        if calls["count"] == 1:
            assert "tools" in payload
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "operation_request",
                                            "arguments": json.dumps({"operation": "list_users_users_get"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        assert any(message["role"] == "tool" for message in payload["messages"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The API returned demo@example.com."}}]},
        )

    async def tool_runner(name: str, args: dict[str, object]) -> dict[str, object]:
        assert name == "operation_request"
        assert args["operation"] == "list_users_users_get"
        return {
            "ok": True,
            "tool_name": name,
            "method": "GET",
            "path": "/users",
            "status": 200,
            "input": args,
            "data": [{"email": "demo@example.com"}],
            "preview": "GET /users -> 200",
        }

    responder = create_deepseek_responder(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        tool_runner=tool_runner,
    )
    response = asyncio.run(
        responder(AgentRequest(message="List users"), build_app().openapi())
    )

    assert response.answer == "The API returned demo@example.com."
    assert response.tool_results[0].tool_name == "operation_request"
    assert response.tool_results[0].status == 200


def test_stream_deepseek_agent_emits_tool_chain_events() -> None:
    calls = {"count": 0}

    def sse(*payloads: dict[str, object]) -> str:
        return "".join("data: " + json.dumps(payload) + "\n\n" for payload in payloads) + "data: [DONE]\n\n"

    async def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=sse(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {"name": "operation_search", "arguments": '{"query":"users"}'},
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ),
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(
                {"choices": [{"delta": {"content": "Users are available."}}]},
            ),
        )

    async def tool_runner(name: str, args: dict[str, object]) -> dict[str, object]:
        return {
            "ok": True,
            "tool_name": name,
            "input": args,
            "data": {"operations": [{"method": "GET", "path": "/users"}]},
            "preview": "Found 1 operation.",
        }

    async def collect() -> list[dict[str, object]]:
        events = []
        async for event in stream_deepseek_agent(
            AgentRequest(message="List users"),
            build_app().openapi(),
            tool_runner,
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())
    event_types = [event["type"] for event in events]

    assert "tool-input-available" in event_types
    assert "tool-output-available" in event_types
    assert "text-delta" in event_types
    assert "finish" in event_types
