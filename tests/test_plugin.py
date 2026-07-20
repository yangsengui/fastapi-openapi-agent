import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from openagent import (
    AgentBackend,
    AgentContext,
    AgentRequest,
    AgentResponse,
    OpenAPIAgent,
    OpenAPIAgentRuntime as CoreOpenAPIAgentRuntime,
    OperationCatalog,
)
from openagent.fastapi import (
    OpenAPIAgentConfig,
    OpenAPIAgentRuntime as FastAPIRuntime,
    install_openapi_agent,
)
from openagent.llm import create_llm_responder, stream_llm_agent


class UserCreate(BaseModel):
    email: str


def request_app(
    app: FastAPI, requests: list[tuple[str, str, dict[str, object]]]
) -> list[httpx.Response]:
    async def send() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return [
                await client.request(method, path, **kwargs)
                for method, path, kwargs in requests
            ]

    return asyncio.run(send())


def build_app() -> FastAPI:
    app = FastAPI(title="Test API")

    @app.get(
        "/users",
        tags=["users"],
        summary="List users",
        description="Return the users visible to the current caller.",
    )
    def list_users() -> list[dict[str, str]]:
        return [{"email": "demo@example.com"}]

    @app.post("/users", tags=["users"], summary="Create user")
    def create_user(payload: UserCreate) -> dict[str, str]:
        return payload.dict()

    install_openapi_agent(app, auto_llm=False)
    return app


def test_agent_serves_page_and_sidebar() -> None:
    page, sidebar = request_app(
        build_app(),
        [("GET", "/_agent/", {}), ("GET", "/_agent/sidebar.js", {})],
    )

    assert page.status_code == 200
    assert "OpenAgent" in page.text
    assert sidebar.status_code == 200
    assert "foa-loader-frame" in sidebar.text
    assert "/widget/" in sidebar.text


def test_agent_config_preserves_responder_positional_argument() -> None:
    def responder(_: AgentRequest, __: dict[str, object]) -> AgentResponse:
        return AgentResponse(answer="custom")

    config = OpenAPIAgentConfig("/_agent", "Title", "Description", responder)

    assert config.responder is responder
    assert config.agent is None


def test_agent_serves_widget_spa() -> None:
    widget = request_app(build_app(), [("GET", "/_agent/widget/", {})])[0]

    assert widget.status_code == 200
    assert "OpenAgent" in widget.text
    assert "/_agent/widget/assets/" in widget.text

def test_core_runtime_searches_openapi_without_fastapi_adapter() -> None:
    runtime = CoreOpenAPIAgentRuntime(build_app().openapi(), enable_api_calls=False)

    result = runtime.operation_search({"query": "create user"})

    assert result["ok"] is True
    assert result["data"]["operations"][0]["path"] == "/users"


def test_operation_catalog_separates_metadata_from_contract_schema() -> None:
    catalog = OperationCatalog.from_openapi(build_app().openapi())

    operations = catalog.list_operations()
    contract = catalog.require_operation("create_user_users_post")

    assert {operation.operation_id for operation in operations} == {
        "list_users_users_get",
        "create_user_users_post",
    }
    assert operations[0].description == "Return the users visible to the current caller."
    assert not hasattr(operations[0], "component_schemas")
    assert contract.metadata.operation_id == "create_user_users_post"
    assert "UserCreate" in contract.component_schemas
    assert "requestBody" in contract.openapi_operation


def test_operation_catalog_merges_path_and_operation_parameters() -> None:
    catalog = OperationCatalog.from_openapi(
        {
            "openapi": "3.1.0",
            "paths": {
                "/items/{item_id}": {
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {"$ref": "#/components/parameters/Tenant~1Alias"},
                    ],
                    "get": {
                        "operationId": "get_item",
                        "parameters": [
                            {
                                "name": "item_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                            },
                            {"name": "expand", "in": "query", "schema": {"type": "boolean"}},
                        ],
                        "responses": {"200": {"description": "OK"}},
                    },
                }
            },
            "components": {
                "parameters": {
                    "Tenant/Alias": {"$ref": "#/components/parameters/TenantHeader"},
                    "TenantHeader": {
                        "name": "tenant_id",
                        "in": "header",
                        "schema": {"$ref": "#/components/schemas/TenantId"},
                    },
                },
                "schemas": {"TenantId": {"type": "string"}},
            },
        }
    )

    contract = catalog.require_operation("get_item")

    assert contract.metadata.parameters == [
        "item_id (path)",
        "tenant_id (header)",
        "expand (query)",
    ]
    assert contract.openapi_operation["parameters"][0]["schema"]["type"] == "integer"
    assert contract.component_schemas == {"TenantId": {"type": "string"}}


def test_operation_catalog_filters_method_before_ranking_limit() -> None:
    catalog = OperationCatalog.from_openapi(
        {
            "openapi": "3.1.0",
            "paths": {
                "/users": {
                    "post": {
                        "operationId": "create_user",
                        "summary": "Create user",
                        "responses": {"201": {"description": "Created"}},
                    },
                    "get": {
                        "operationId": "list_users",
                        "summary": "List users",
                        "responses": {"200": {"description": "OK"}},
                    },
                }
            },
        }
    )

    matches = catalog.search_operations("create users", method="GET", limit=1)

    assert [operation.operation_id for operation in matches] == ["list_users"]


def test_agent_exposes_host_openapi_schema() -> None:
    response = request_app(build_app(), [("GET", "/_agent/openapi", {})])[0]

    assert response.status_code == 200
    assert "/users" in response.json()["paths"]
    assert "/_agent/chat" not in response.json()["paths"]


def test_agent_chat_returns_matching_operations() -> None:
    response = request_app(
        build_app(),
        [("POST", "/_agent/chat", {"json": {"message": "How do I create a user?"}})],
    )[0]

    assert response.status_code == 200
    body = response.json()
    assert "POST /users" in body["answer"]
    assert body["operations"][0]["path"] == "/users"


class CatalogAgentBackend(AgentBackend):
    async def respond(self, context: AgentContext) -> AgentResponse:
        operation = context.catalog.search_operations(context.request.message, limit=1)[0]
        contract = await context.run_tool(
            "operation_get", {"operationId": operation.operation_id}
        )
        result = await context.run_tool(
            "operation_request", {"operationId": operation.operation_id}
        )
        return AgentResponse(
            answer=(
                f"Selected {operation.method} {operation.path}: {contract['preview']} "
                f"Returned {len(result['data'])} project."
            ),
            sources=[f"{operation.method} {operation.path}"],
        )


def build_sdk_app() -> FastAPI:
    app = FastAPI(title="SDK Test API")

    @app.get("/projects", summary="List projects")
    def list_projects() -> list[dict[str, str]]:
        return [{"name": "OpenAgent"}]

    install_openapi_agent(
        app,
        agent=OpenAPIAgent(CatalogAgentBackend()),
        auto_llm=False,
    )
    return app


def test_custom_agent_sdk_handles_json_and_stream_routes() -> None:
    response, stream = request_app(
        build_sdk_app(),
        [
            ("POST", "/_agent/chat", {"json": {"message": "list projects"}}),
            ("POST", "/_agent/chat/stream", {"json": {"message": "list projects"}}),
        ],
    )

    assert response.status_code == 200
    assert response.json()["answer"].startswith("Selected GET /projects")
    assert "Returned 1 project" in response.json()["answer"]
    assert '"type": "start"' in stream.text
    assert '"messageId": "assistant_' in stream.text
    assert '"type": "text-delta"' in stream.text
    assert '"type": "finish"' in stream.text
    assert stream.text.endswith("data: [DONE]\n\n")


def test_agent_stream_endpoint_falls_back_to_responder() -> None:
    response = request_app(
        build_app(),
        [
            (
                "POST",
                "/_agent/chat/stream",
                {"json": {"message": "How do I create a user?"}},
            )
        ],
    )[0]

    assert response.status_code == 200
    assert "text-delta" in response.text
    assert "finish" in response.text
    assert "POST /users" in response.text


def test_llm_responder_calls_litellm_with_provider_neutral_config() -> None:
    captured: dict[str, object] = {}

    async def completion(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "Use POST /users to create a user."}}]}

    responder = create_llm_responder(
        model="openai/gpt-4o-mini",
        api_key="test-key",
        base_url="https://gateway.example.com/v1",
        completion=completion,
    )
    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://gateway.example.com/v1"
    assert captured["model"] == "openai/gpt-4o-mini"
    assert captured["stream"] is False
    assert "temperature" not in captured
    assert "tool_choice" not in captured
    assert captured["tools"][0]["function"]["name"] == "operation_search"
    context_text = captured["messages"][-1]["content"]
    context = json.loads(context_text.split("Relevant OpenAPI context:\n", 1)[1])
    assert {operation["operationId"] for operation in context["operations"]} == {
        "list_users_users_get",
        "create_user_users_post",
    }
    assert context["operations"][0]["summary"] == "List users"
    assert context["operations"][0]["description"] == "Return the users visible to the current caller."
    assert "UserCreate" not in context_text
    assert "component_schemas" not in context_text
    assert "POST /users" in response.answer
    assert response.operations[0].path == "/users"


def test_llm_responder_handles_real_litellm_model_response(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    pytest.importorskip("litellm")
    responder = create_llm_responder(
        model="openai/gpt-4o-mini",
        model_kwargs={"mock_response": "Real LiteLLM response."},
    )

    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert response.answer == "Real LiteLLM response."


def test_fastapi_auto_llm_uses_configured_model(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def completion(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "Configured model response."}}]}

    monkeypatch.setattr("openagent.llm._litellm_completion", completion)
    app = FastAPI(title="Configured LLM API")

    @app.get("/status", summary="Get status")
    def status() -> dict[str, bool]:
        return {"ok": True}

    install_openapi_agent(
        app,
        llm_model="openai/gpt-4o-mini",
        llm_api_key="configured-key",
    )

    response = request_app(
        app,
        [("POST", "/_agent/chat", {"json": {"message": "Is it healthy?"}})],
    )[0]

    assert response.status_code == 200
    assert response.json()["answer"] == "Configured model response."
    assert captured["model"] == "openai/gpt-4o-mini"
    assert captured["api_key"] == "configured-key"


def test_llm_responder_falls_back_on_api_error() -> None:
    class APIError(Exception):
        status_code = 401

    async def completion(**_: object) -> dict[str, object]:
        raise APIError

    responder = create_llm_responder(
        model="anthropic/claude-sonnet-4-5",
        completion=completion,
    )
    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert "LLM request failed with HTTP 401" in response.answer
    assert "POST /users" in response.answer


def test_llm_responder_adds_provider_prefix_for_bare_model_name() -> None:
    captured: dict[str, object] = {}

    async def completion(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "DeepSeek response."}}]}

    responder = create_llm_responder(
        model="deepseek-chat",
        api_key="deepseek-key",
        completion=completion,
    )
    response = asyncio.run(
        responder(AgentRequest(message="How do I create a user?"), build_app().openapi())
    )

    assert captured["model"] == "deepseek/deepseek-chat"
    assert captured["api_key"] == "deepseek-key"
    assert response.answer == "DeepSeek response."


def test_llm_responder_without_runner_can_load_contract() -> None:
    calls = {"count": 0}

    async def completion(**kwargs: object) -> dict[str, object]:
        payload = kwargs
        calls["count"] += 1
        assert "tools" in payload
        if calls["count"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_contract",
                                    "type": "function",
                                    "function": {
                                        "name": "operation_get",
                                        "arguments": json.dumps(
                                            {"operationId": "create_user_users_post"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        assert payload["messages"][-1]["role"] == "tool"
        assert "UserCreate" in payload["messages"][-1]["content"]
        return {"choices": [{"message": {"content": "The body requires an email."}}]}

    responder = create_llm_responder(
        model="openai/gpt-4o-mini",
        completion=completion,
    )
    response = asyncio.run(
        responder(AgentRequest(message="What does create user require?"), build_app().openapi())
    )

    assert response.answer == "The body requires an email."
    assert response.tool_results[0].tool_name == "operation_get"


def test_llm_can_load_operation_without_operation_id() -> None:
    calls = {"count": 0}
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": "No IDs", "version": "1"},
        "paths": {
            "/status": {
                "get": {
                    "summary": "Get status",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Status"}
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Status": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                }
            }
        },
    }

    async def completion(**kwargs: object) -> dict[str, object]:
        payload = kwargs
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_status",
                                    "type": "function",
                                    "function": {
                                        "name": "operation_get",
                                        "arguments": json.dumps(
                                            {"method": "GET", "path": "/status"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        assert "Status" in payload["messages"][-1]["content"]
        return {"choices": [{"message": {"content": "Status returns an ok boolean."}}]}

    responder = create_llm_responder(
        model="gemini/gemini-2.5-flash",
        completion=completion,
    )
    response = asyncio.run(responder(AgentRequest(message="What does status return?"), openapi))

    assert response.answer == "Status returns an ok boolean."
    assert response.tool_results[0].path == "/status"


def test_llm_context_respects_catalog_budget() -> None:
    captured: dict[str, object] = {}
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Large API", "version": "1"},
        "paths": {
            f"/resources/{index}": {
                "get": {
                    "operationId": f"get_resource_{index}",
                    "summary": f"Get resource {index}",
                    "description": "A detailed operation description. " * 10,
                    "responses": {"200": {"description": "OK"}},
                }
            }
            for index in range(20)
        },
    }

    async def completion(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "Use search."}}]}

    responder = create_llm_responder(
        model="openrouter/openai/gpt-4o-mini",
        max_context_chars=600,
        completion=completion,
    )
    asyncio.run(responder(AgentRequest(message="Get a resource"), openapi))

    content = captured["messages"][-1]["content"]
    context_json = content.split("Relevant OpenAPI context:\n", 1)[1]
    context = json.loads(context_json)
    assert len(context_json) <= 600
    assert context["catalogComplete"] is False
    assert context["totalOperations"] == 20


def test_runtime_can_execute_readonly_host_api() -> None:
    app = build_app()
    runtime = FastAPIRuntime(app, app.openapi(), agent_path="/_agent")

    async def execute() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        blocked = await runtime.run_tool(
            "operation_request", {"operationId": "list_users_users_get"}
        )
        loaded = await runtime.run_tool(
            "operation_get", {"operationId": "list_users_users_get"}
        )
        result = await runtime.run_tool(
            "operation_request", {"operationId": "list_users_users_get"}
        )
        return blocked, loaded, result

    blocked, loaded, result = asyncio.run(execute())

    assert blocked["ok"] is False
    assert "operation_get" in blocked["error"]
    assert loaded["ok"] is True
    assert loaded["data"]["openapi_operation"]["responses"]
    assert result["ok"] is True
    assert result["method"] == "GET"
    assert result["status"] == 200
    assert result["data"] == [{"email": "demo@example.com"}]


def test_llm_responder_runs_tool_call_loop() -> None:
    calls = {"count": 0}

    async def completion(**kwargs: object) -> dict[str, object]:
        payload = kwargs
        calls["count"] += 1
        if calls["count"] == 1:
            assert "tools" in payload
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "operation_get",
                                        "arguments": json.dumps(
                                            {"operationId": "list_users_users_get"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        if calls["count"] == 2:
            assert payload["messages"][-1]["name"] == "operation_get"
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "operation_request",
                                        "arguments": json.dumps(
                                            {"operationId": "list_users_users_get"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        assert any(message["role"] == "tool" for message in payload["messages"])
        return {"choices": [{"message": {"content": "The API returned demo@example.com."}}]}

    async def tool_runner(name: str, args: dict[str, object]) -> dict[str, object]:
        assert args["operationId"] == "list_users_users_get"
        if name == "operation_get":
            return {
                "ok": True,
                "tool_name": name,
                "method": "GET",
                "path": "/users",
                "input": args,
                "data": {"openapi_operation": {"responses": {"200": {}}}},
                "preview": "Loaded contract for GET /users.",
            }
        assert name == "operation_request"
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

    responder = create_llm_responder(
        model="anthropic/claude-sonnet-4-5",
        completion=completion,
        tool_runner=tool_runner,
    )
    response = asyncio.run(
        responder(AgentRequest(message="List users"), build_app().openapi())
    )

    assert response.answer == "The API returned demo@example.com."
    assert [result.tool_name for result in response.tool_results] == ["operation_get", "operation_request"]
    assert response.tool_results[1].status == 200


def test_stream_llm_agent_emits_tool_chain_events() -> None:
    calls = {"count": 0}
    tool_calls: list[str] = []

    async def completion(**kwargs: object):
        calls["count"] += 1
        assert kwargs["model"] == "openai/gpt-4o-mini"
        assert kwargs["stream"] is True
        if calls["count"] == 1:
            chunks = [
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "Checking the contract. ",
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "type": "function",
                                        "function": {
                                            "name": "operation_",
                                            "arguments": '{"operationId":"list_',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "name": "get",
                                            "arguments": 'users_users_get"}',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            ]
        else:
            assistant_call = kwargs["messages"][-2]["tool_calls"][0]
            tool_result = kwargs["messages"][-1]
            assert assistant_call["id"] == tool_result["tool_call_id"]
            chunks = [{"choices": [{"delta": {"content": "Users are available."}}]}]

        async def stream():
            for chunk in chunks:
                yield chunk

        return stream()

    async def tool_runner(name: str, args: dict[str, object]) -> dict[str, object]:
        tool_calls.append(name)
        return {
            "ok": True,
            "tool_name": name,
            "input": args,
            "data": {"openapi_operation": {"responses": {"200": {}}}},
            "preview": "Loaded contract for GET /users.",
        }

    async def collect() -> list[dict[str, object]]:
        events = []
        async for event in stream_llm_agent(
            AgentRequest(message="List users"),
            build_app().openapi(),
            tool_runner,
            model="openai/gpt-4o-mini",
            completion=completion,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())
    event_types = [event["type"] for event in events]

    assert "tool-input-available" in event_types
    assert "tool-output-available" in event_types
    assert "text-delta" in event_types
    assert "finish" in event_types
    assert tool_calls == ["operation_get"]
    assert event_types.index("text-end") < event_types.index("tool-input-start")
    assert event_types.count("text-start") == 2
    assert event_types.count("text-end") == 2


def test_stream_llm_agent_converts_tool_runner_exception_to_error_events() -> None:
    async def completion(**_: object):
        async def stream():
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_failed",
                                    "type": "function",
                                    "function": {
                                        "name": "operation_get",
                                        "arguments": '{"operationId":"list_users_users_get"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }

        return stream()

    async def tool_runner(_: str, __: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("runner failed")

    async def collect() -> list[dict[str, object]]:
        return [
            event
            async for event in stream_llm_agent(
                AgentRequest(message="List users"),
                build_app().openapi(),
                tool_runner,
                model="openai/gpt-4o-mini",
                completion=completion,
            )
        ]

    events = asyncio.run(collect())
    event_types = [event["type"] for event in events]

    assert event_types[-2:] == ["tool-output-error", "error"]
    assert "finish" not in event_types
    assert events[-1]["errorText"] == "Tool execution failed: RuntimeError."
