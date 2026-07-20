# OpenAgent

[![Documentation](https://img.shields.io/badge/docs-online-4051b5?logo=materialformkdocs&logoColor=white)](https://yangsengui.github.io/fastapi-openapi-agent/)
[![Documentation CI](https://github.com/yangsengui/fastapi-openapi-agent/actions/workflows/docs.yml/badge.svg)](https://github.com/yangsengui/fastapi-openapi-agent/actions/workflows/docs.yml)

OpenAgent is an OpenAPI-native API agent for FastAPI. It mounts an assistant on top of an existing FastAPI app, reads the app's OpenAPI schema, and can answer questions, inspect operation contracts, and optionally execute host API calls in-process through ASGI.

The PyPI distribution name is `fastapi-openapi-agent`. The Python import package is `openagent`.

> Status: alpha. APIs may change before the first stable release.

Documentation: [Online documentation](https://yangsengui.github.io/fastapi-openapi-agent/) · [5-minute quickstart](https://yangsengui.github.io/fastapi-openapi-agent/getting-started/) · [OpenAPI quality guide](https://yangsengui.github.io/fastapi-openapi-agent/guides/openapi-quality/)

## Features

- One-line FastAPI integration with `install_openapi_agent(app)`.
- Framework-neutral OpenAPI runtime for operation search, contract lookup, and tool execution.
- Built-in agent page at `/_agent/` and embeddable widget at `/_agent/widget/`.
- Static sidebar loader at `/_agent/sidebar.js` for adding a floating API assistant to any page.
- SSE chat endpoint at `/_agent/chat/stream` with text deltas and tool-call events.
- JSON fallback endpoint at `/_agent/chat`.
- Local deterministic OpenAPI responder for offline development.
- LiteLLM responder for DeepSeek, OpenAI, Anthropic, Gemini, Azure, and other providers.
- In-process host API execution through `httpx.ASGITransport`; no public HTTP round trip is required.
- Parent-page request bridge for custom auth, tenant headers, request signing, or token refresh.

## Installation

Install the FastAPI adapter:

```bash
pip install "fastapi-openapi-agent[fastapi]"
```

Add the LiteLLM integration when using an external model:

```bash
pip install "fastapi-openapi-agent[fastapi,llm]"
```

For local development from source:

```bash
pip install -e ".[dev,llm]"
npm install --prefix frontend
npm run build --prefix frontend
```

The frontend build step generates `src/openagent/static/sidebar.js` and `src/openagent/static/widget/`. These files are included in the Python wheel so users installing from PyPI do not need Node.js.

## Quick Start

```python
from fastapi import FastAPI
from openagent.fastapi import install_openapi_agent

app = FastAPI(title="My API")

install_openapi_agent(app)
```

Start your FastAPI app and open:

- `/_agent/` for the standalone agent page.
- `/_agent/widget/` for the widget SPA.
- `/_agent/sidebar.js` for the embeddable sidebar loader.
- `/docs` for the normal FastAPI Swagger UI.

## FastAPI Integration

Customize the route prefix and UI metadata:

```python
install_openapi_agent(
    app,
    path="/api-agent",
    title="Service Agent",
    description="Ask questions about this service API.",
)
```

Enable live host API calls:

```python
install_openapi_agent(
    app,
    enable_api_calls=True,
    allow_mutating_api_calls=False,
)
```

By default, live execution only allows `GET`, `HEAD`, and `OPTIONS`. If your product explicitly allows write operations, enable mutating calls:

```python
install_openapi_agent(app, allow_mutating_api_calls=True)
```

## Frontend Embed

Add a floating sidebar to any page served by the same app:

```html
<script src="/_agent/sidebar.js"></script>
```

Configure cross-path or cross-origin embedding:

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    title: "API Assistant",
    open: false,
    width: 560,
    minWidth: 420,
    maxWidth: 920
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

Embed the widget into a container instead of using a floating drawer:

```html
<div id="agent-root"></div>
<script>
  window.OpenAgent = {
    baseUrl: "/_agent",
    container: "#agent-root"
  };
</script>
<script src="/_agent/sidebar.js"></script>
```

The sidebar supports resizing, persists the chosen width, and can be toggled with `Ctrl/Cmd + E`.

## Custom Request Bridge

If the host product already has a frontend request layer, provide `window.OpenAgent.request`. The widget runs inside an iframe, so `sidebar.js` bridges iframe requests to the parent page and lets your code execute the actual request.

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    async request(input) {
      const token = await getAccessToken();

      return fetch(input.url, {
        method: input.method,
        headers: {
          ...input.headers,
          Authorization: `Bearer ${token}`,
          "X-Tenant-ID": getTenantId()
        },
        body: input.body,
        credentials: "include"
      });
    }
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

`request(input)` must return a standard `fetch` `Response`. The bridge covers `/_agent/chat/stream` and `/_agent/chat`. Stream responses are forwarded to the iframe chunk by chunk. For safety, the bridge only allows requests under the configured `baseUrl`.

## Authentication

There are two separate auth concerns.

Protect the agent routes with your normal FastAPI authentication layer, for example by mounting the agent behind authenticated middleware, a protected router, or reverse-proxy auth.

Forward the current user identity when the agent calls host APIs. The FastAPI adapter forwards selected headers into in-process API calls:

```python
install_openapi_agent(
    app,
    forward_headers=("authorization", "cookie"),
    allow_mutating_api_calls=False,
)
```

If your frontend is cross-origin, the request bridge is usually the safest place to attach JWTs, cookies, tenant IDs, or gateway signatures.

## Multi-Provider LLM Integration

OpenAgent uses [LiteLLM](https://docs.litellm.ai/) as its provider-neutral model layer. LiteLLM exposes one OpenAI-style Python API for DeepSeek, OpenAI, Anthropic, Gemini, Azure, Bedrock, OpenRouter, Ollama, and other providers. The default OpenAgent responder remains deterministic and makes no external request until a model is configured.

Set `OPENAGENT_MODEL` to a LiteLLM model name and provide that provider's normal credentials. OpenAgent then enables the model responder automatically:

```bash
# DeepSeek
export OPENAGENT_MODEL="deepseek/deepseek-chat"
export DEEPSEEK_API_KEY="your-api-key"

# OpenAI
export OPENAGENT_MODEL="openai/gpt-4o-mini"
export OPENAI_API_KEY="your-api-key"

# Anthropic
export OPENAGENT_MODEL="anthropic/claude-sonnet-4-5"
export ANTHROPIC_API_KEY="your-api-key"

# Gemini
export OPENAGENT_MODEL="gemini/gemini-2.5-flash"
export GEMINI_API_KEY="your-api-key"
```

Only configure one model for a running application. The examples are alternatives, not a single combined configuration.

The same options can be passed directly to the FastAPI adapter:

```python
from openagent.fastapi import install_openapi_agent

install_openapi_agent(
    app,
    llm_model="openai/gpt-4o-mini",
    llm_api_key="your-api-key",  # Prefer a secret environment variable in production.
)
```

For a LiteLLM Proxy or another OpenAI-compatible gateway, set a custom base URL:

```bash
export OPENAGENT_MODEL="openai/my-model"
export OPENAGENT_API_KEY="gateway-key"
export OPENAGENT_BASE_URL="http://localhost:4000/v1"
```

Provider-specific LiteLLM options can be supplied through `llm_model_kwargs`:

```python
install_openapi_agent(
    app,
    llm_model="azure/my-deployment",
    llm_model_kwargs={"api_version": "2024-10-21"},
)
```

Or create a responder explicitly:

```python
from openagent import create_llm_responder
from openagent.fastapi import install_openapi_agent

responder = create_llm_responder(model="openrouter/openai/gpt-4o-mini")
install_openapi_agent(app, responder=responder)
```

The explicit responder can search operations and load contracts locally. Because it has no host application invoker, live `operation_request` calls remain disabled. Use automatic LiteLLM integration or a custom `OpenAPIAgent` backend when live host API execution is required. Select a model that supports tool calling.

A bare model name without a provider prefix is treated as a DeepSeek model, so `deepseek-chat` is normalized to `deepseek/deepseek-chat`. New code should use `create_llm_responder` and `stream_llm_agent`.

For large APIs, the initial metadata catalog is compacted to `max_context_chars`. If every operation cannot fit, the context sets `catalogComplete` to `false` and the model uses `operation_search` before loading the selected contract. Operations without an `operationId` are addressed by method and path.

The model initially receives a compact catalog of every operation's metadata, including method, path, operationId, summary, description, tags, parameter names, and response status codes. Request and response schemas are not included in that initial context. The selected operation's full contract and referenced schemas are loaded on demand with `operation_get`.

When tool calling is enabled, the required API execution chain is:

```text
operation_get -> operation_request -> final answer
```

`operation_search` remains available as an optional catalog filter. The runtime rejects `operation_request` unless the same operation was first loaded with `operation_get` during that agent run.

## Custom Responder

You can replace the built-in responder with your own LLM, internal agent platform, or policy layer:

```python
from openagent import AgentRequest, AgentResponse
from openagent.fastapi import install_openapi_agent

async def my_responder(request: AgentRequest, openapi: dict) -> AgentResponse:
    return AgentResponse(
        answer="LLM response",
        operations=[],
        sources=[],
    )

install_openapi_agent(app, responder=my_responder)
```

## Custom Agent SDK

Use the core SDK when a custom implementation needs operation discovery, detailed contracts, runtime tools, and the standard JSON/SSE routes. `OperationCatalog` keeps schema-free metadata separate from contracts loaded on demand.

```python
from openagent import (
    AgentBackend,
    AgentContext,
    AgentResponse,
    OpenAPIAgent,
)
from openagent.fastapi import install_openapi_agent


class MyAgentBackend(AgentBackend):
    async def respond(self, context: AgentContext) -> AgentResponse:
        matches = context.catalog.search_operations(
            context.request.message,
            limit=1,
        )
        if not matches or not matches[0].operation_id:
            return AgentResponse(answer="No matching operation was found.")

        operation = matches[0]
        contract = await context.run_tool(
            "operation_get",
            {"operationId": operation.operation_id},
        )
        return AgentResponse(
            answer=f"Selected {operation.method} {operation.path}: {contract['preview']}",
            sources=[f"{operation.method} {operation.path}"],
        )


agent = OpenAPIAgent(MyAgentBackend())
install_openapi_agent(app, agent=agent)
```

Implementing `respond` is sufficient: `AgentBackend` converts it to the standard SSE event sequence automatically. Override `stream` to emit incremental typed events such as `TextDeltaEvent`, `ToolInputAvailableEvent`, and `ToolOutputAvailableEvent`.

The catalog can also be used independently of FastAPI:

```python
from openagent import OperationCatalog

catalog = OperationCatalog.from_openapi(openapi_document)
metadata = catalog.list_operations()
matches = catalog.search_operations("create user")
contract = catalog.require_operation("create_user_users_post")
```

`OperationMetadata` contains no request or response schemas. `OperationContract` contains the selected operation, merged path-level parameters, risk metadata, and all referenced component schemas.

## Local Demo

With devyard:

```bash
devyard run install
devyard run build
devyard up
devyard status
```

Without devyard:

```bash
pip install -e ".[dev]"
npm install --prefix frontend
npm run build --prefix frontend
python -m uvicorn examples.demo:app --reload
```

Then open `http://127.0.0.1:8000/_agent/`.

## Development

```bash
npm run check --prefix frontend
npm run build --prefix frontend
pytest
```

Full local validation:

```bash
npm run check --prefix frontend && npm run build --prefix frontend && pytest
```

## Packaging

Build and inspect the Python distributions:

```bash
pip install -e ".[dev]"
npm run build --prefix frontend
python -m build
python -m twine check dist/*
```

Inspect the wheel contents before publishing:

```bash
python -m zipfile -l dist/fastapi_openapi_agent-*.whl
```

The wheel should include:

- `openagent/static/sidebar.js`
- `openagent/static/widget/index.html`
- `openagent/static/widget/assets/...`
- `openagent/py.typed`

## PyPI Release

This repository includes `.github/workflows/publish.yml` for token-free [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/). A published GitHub release automatically runs the frontend checks, Python tests, package build, `twine` validation, and PyPI upload. The release tag must match the version in `pyproject.toml`; both `0.1.0` and `v0.1.0` tag formats are accepted.

Before the first release, configure a trusted publisher on PyPI with:

- PyPI project name: `fastapi-openapi-agent`
- GitHub owner: `yangsengui`
- GitHub repository: `fastapi-openapi-agent`
- Workflow filename: `publish.yml`
- Environment name: `pypi`

Create a `pypi` environment under the GitHub repository's **Settings > Environments** page. Environment reviewers are optional, but recommended when manual approval is required before production publication. No `PYPI_API_TOKEN` secret is needed.

Recommended release flow:

1. Update `version` in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Run the packaging checks above.
4. Commit and push the release changes.
5. Create and publish a GitHub release using a matching tag such as `v0.1.0`.
6. Verify the `Publish Python Package` workflow and the release on PyPI.

The workflow can also be started manually from **Actions > Publish Python Package > Run workflow**. By default, a manual run only tests and builds the distributions without publishing them. Enable the `publish` input to upload the version declared by the selected branch; PyPI rejects a version that has already been uploaded.

Manual upload is also possible:

```bash
python -m twine upload dist/*
```

## License

MIT. See `LICENSE`.
