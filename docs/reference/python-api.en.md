# Python API

## `install_openapi_agent`

```python
from openagent.fastapi import install_openapi_agent

router = install_openapi_agent(app, config=None, **overrides)
```

Mounts the Agent router on an existing FastAPI application and returns the `APIRouter`. Pass an `OpenAPIAgentConfig` object or use keyword overrides.

For Django Ninja, import the adapter from its framework module:

```python
from openagent.django_ninja import install_openapi_agent

router = install_openapi_agent(api, config=None, **overrides)
```

This attaches a Ninja `Router` to the existing `NinjaAPI`. Mount `api.urls` in Django normally; the adapter includes the Django URL prefix in widget and OpenAPI operation paths automatically.

## `OpenAPIAgentConfig`

The canonical FastAPI options and defaults live in [`src/openagent/fastapi.py`](https://github.com/yangsengui/fastapi-openapi-agent/blob/main/src/openagent/fastapi.py). Django Ninja uses the equivalent config from `openagent.django_ninja`, with additional `openapi_path_prefix` and `asgi_app` options. See [Configuration and models](../guides/configuration.md) for the commonly used settings.

## `OperationCatalog`

Search an OpenAPI document without depending on FastAPI:

```python
from openagent import OperationCatalog

catalog = OperationCatalog.from_openapi(openapi_document)
all_operations = catalog.list_operations()
matches = catalog.search_operations("create a user", method="POST", limit=5)
contract = catalog.require_operation("create_user")
```

`OperationMetadata` contains compact discovery data only. `OperationContract` contains the selected operation, its risk classification, and referenced component schemas.

## `OpenAPIAgentRuntime`

The runtime exposes three standard tools:

| Tool | Purpose |
| --- | --- |
| `operation_search` | Search operations by natural language, method, or operationId |
| `operation_get` | Load the exact contract of a selected operation |
| `operation_request` | Execute a previously loaded operation when policy allows |

Framework-neutral usage:

```python
from openagent import OpenAPIAgentRuntime

runtime = OpenAPIAgentRuntime(openapi_document, enable_api_calls=False)
result = runtime.operation_search({"query": "list orders"})
```

To execute a live API, an adapter must provide an invoker implementing the `OperationInvoker` protocol.

## Custom Agent SDK

```python
from openagent import AgentBackend, AgentContext, AgentResponse, OpenAPIAgent


class MyBackend(AgentBackend):
    async def respond(self, context: AgentContext) -> AgentResponse:
        matches = context.catalog.search_operations(context.request.message, limit=1)
        if not matches:
            return AgentResponse(answer="No matching operation was found.")

        selected = matches[0]
        contract = await context.run_tool(
            "operation_get",
            {"operationId": selected.operation_id},
        )
        return AgentResponse(answer=contract["preview"])


agent = OpenAPIAgent(MyBackend())
install_openapi_agent(app, agent=agent)
```

Implementing `respond` is enough to receive the standard SSE event sequence. Override `stream` and emit `TextDeltaEvent`, `ToolInputAvailableEvent`, `ToolOutputAvailableEvent`, and related typed events for true incremental output.

## LiteLLM helpers

```python
from openagent import create_llm_responder, stream_llm_agent
```

`create_llm_responder` creates a JSON responder. `stream_llm_agent` emits UI-ready streaming events. Both require the `llm` optional dependency.
