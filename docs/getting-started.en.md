# Build your first API Agent in 5 minutes

This guide starts with an existing FastAPI application and adds OpenAgent with one line of Python.

## 1. Install

=== "With an LLM"

    ```bash
    pip install "fastapi-openapi-agent[fastapi,llm]"
    ```

=== "Local capabilities only"

    ```bash
    pip install "fastapi-openapi-agent[fastapi]"
    ```

Without a configured model, the built-in deterministic responder can still search operations and support local integration testing. A model is required for full natural-language reasoning and multi-step tool use.

## 2. Define a high-quality endpoint

```python title="app.py"
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int = Field(description="Unique inventory item ID", example=42)
    name: str = Field(description="Display name", example="Router")
    owner: str = Field(description="Team responsible for the item", example="network")


app = FastAPI(
    title="Inventory API",
    version="1.0.0",
    description="Query and manage inventory assets in the organization.",
)


@app.get(
    "/items",
    operation_id="list_inventory_items",
    summary="List inventory items",
    description="Return items visible to the current caller, optionally filtered by owner team.",
    tags=["inventory"],
    response_model=List[Item],
    responses={401: {"description": "The caller is not authenticated"}},
)
def list_items(
    owner: Optional[str] = Query(
        default=None,
        description="Return only items owned by this team",
        example="network",
    ),
) -> List[Item]:
    return [Item(id=42, name="Router", owner=owner or "network")]
```

A stable `operation_id`, an action-oriented `summary`, a business-aware `description`, and useful field descriptions directly improve tool selection and argument generation.

## 3. Mount the Agent

Add this at the end of the same file:

```python
from openagent.fastapi import install_openapi_agent

install_openapi_agent(app)
```

## 4. Configure a model

Choose one tool-calling model configuration:

=== "OpenAI"

    ```bash
    export OPENAGENT_MODEL="openai/gpt-4o-mini"
    export OPENAI_API_KEY="your-api-key"
    ```

=== "DeepSeek"

    ```bash
    export OPENAGENT_MODEL="deepseek/deepseek-chat"
    export DEEPSEEK_API_KEY="your-api-key"
    ```

=== "OpenAI-compatible gateway"

    ```bash
    export OPENAGENT_MODEL="openai/my-model"
    export OPENAGENT_API_KEY="gateway-key"
    export OPENAGENT_BASE_URL="https://gateway.example.com/v1"
    ```

## 5. Run and verify

```bash
uvicorn app:app --reload
```

Open:

- `http://127.0.0.1:8000/_agent/` for the standalone Agent page;
- `http://127.0.0.1:8000/_agent/widget/` for the widget;
- `http://127.0.0.1:8000/docs` for FastAPI's Swagger UI;
- `http://127.0.0.1:8000/_agent/openapi` for the exact OpenAPI snapshot seen by the Agent.

Try asking:

> Which inventory items belong to the network team?

The Agent selects `list_inventory_items`, loads its full contract, and calls `GET /items?owner=network` inside the host ASGI application.

!!! warning "Mutating operations are disabled by default"

    `POST`, `PUT`, `PATCH`, and `DELETE` operations do not run by default. Read [Authentication and security](guides/security.md) before enabling them.

Next, audit your real API with the [OpenAPI quality guide](guides/openapi-quality.md), then review [model and runtime configuration](guides/configuration.md).
