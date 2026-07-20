# Configuration and models

## FastAPI configuration

```python
from openagent.fastapi import OpenAPIAgentConfig, install_openapi_agent

config = OpenAPIAgentConfig(
    path="/_agent",
    title="Orders Agent",
    welcome_title="What would you like to know about your orders?",
    description="Query orders, inspect API capabilities, and call authorized operations.",
    language="en",
    expose_openapi=True,
    enable_api_calls=True,
    allow_mutating_api_calls=False,
    forward_headers=("authorization", "cookie"),
)

install_openapi_agent(app, config)
```

| Option | Default | Description |
| --- | --- | --- |
| `path` | `/_agent` | Agent route prefix |
| `title` | `OpenAgent` | Page and widget title |
| `welcome_title` | `None` | Welcome heading |
| `description` | Built-in copy | User-facing capability boundary |
| `language` | `en` | `en` or `zh`; affects both the UI and model instructions |
| `include_in_schema` | `False` | Include the Agent's own routes in the host OpenAPI document |
| `expose_openapi` | `True` | Expose the `{path}/openapi` snapshot |
| `enable_api_calls` | `True` | Allow calls to host API operations |
| `allow_mutating_api_calls` | `False` | Allow non-read-only operations |
| `auto_llm` | `True` | Enable LiteLLM automatically when a model is configured |
| `forward_headers` | authorization, cookie | Header allowlist forwarded to in-process requests |

Keyword arguments can be passed directly for shorter configurations:

```python
install_openapi_agent(
    app,
    path="/api-agent",
    language="en",
    allow_mutating_api_calls=False,
)
```

## Model environment variables

| Variable | Purpose |
| --- | --- |
| `OPENAGENT_MODEL` | LiteLLM model name, for example `openai/gpt-4o-mini` |
| `OPENAGENT_API_KEY` | Generic or gateway API key |
| `OPENAGENT_BASE_URL` | OpenAI-compatible gateway URL |
| Provider variables | For example `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` |

Configuration can also be supplied in code:

```python
install_openapi_agent(
    app,
    llm_model="openai/my-model",
    llm_api_key="gateway-key",
    llm_base_url="https://gateway.example.com/v1",
    llm_model_kwargs={"num_retries": 2},
)
```

Do not commit model credentials. Use a secret manager or encrypted deployment environment variables in production.

## Large APIs

The initial LiteLLM operation catalog is constrained by `max_context_chars`; full contracts are always loaded on demand. A custom responder can tune the limits:

```python
from openagent import create_llm_responder

responder = create_llm_responder(
    model="openai/my-model",
    max_context_chars=24000,
    max_tool_rounds=6,
    timeout=45,
)
```

An explicitly created responder has no host FastAPI invoker, so it can search and inspect contracts but cannot execute the live API. Use automatic LLM integration or a custom SDK backend when execution is required.

## Custom responder

```python
from openagent import AgentRequest, AgentResponse


async def responder(request: AgentRequest, openapi: dict) -> AgentResponse:
    return AgentResponse(answer="Response from an internal Agent platform")


install_openapi_agent(app, responder=responder)
```

`agent` and `responder` cannot be configured at the same time.
