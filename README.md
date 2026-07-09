# OpenAgent

OpenAgent is an OpenAPI-native API agent for FastAPI. It mounts an assistant on top of an existing FastAPI app, reads the app's OpenAPI schema, and can answer questions, inspect operation contracts, and optionally execute host API calls in-process through ASGI.

The PyPI distribution name is `fastapi-openapi-agent`. The Python import package is `openagent`.

> Status: alpha. APIs may change before the first stable release.

## Features

- One-line FastAPI integration with `install_openapi_agent(app)`.
- Framework-neutral OpenAPI runtime for operation search, contract lookup, and tool execution.
- Built-in agent page at `/_agent/` and embeddable widget at `/_agent/widget/`.
- Static sidebar loader at `/_agent/sidebar.js` for adding a floating API assistant to any page.
- SSE chat endpoint at `/_agent/chat/stream` with text deltas and tool-call events.
- JSON fallback endpoint at `/_agent/chat`.
- Local deterministic OpenAPI responder for offline development.
- DeepSeek responder with tool calling for `operation_search`, `operation_get`, and `operation_request`.
- In-process host API execution through `httpx.ASGITransport`; no public HTTP round trip is required.
- Parent-page request bridge for custom auth, tenant headers, request signing, or token refresh.

## Installation

Install the FastAPI adapter:

```bash
pip install "fastapi-openapi-agent[fastapi]"
```

For local development from source:

```bash
pip install -e ".[dev]"
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

## DeepSeek LLM Integration

The default responder does not call an external model. It uses deterministic OpenAPI matching so local development works without credentials.

Set `DEEPSEEK_API_KEY` to enable the built-in DeepSeek responder automatically:

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

Or configure it explicitly:

```python
from openagent.deepseek import create_deepseek_responder
from openagent.fastapi import install_openapi_agent

install_openapi_agent(app, responder=create_deepseek_responder())
```

When tool calling is enabled, the expected API execution chain is:

```text
operation_search -> operation_get -> operation_request -> final answer
```

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

## Local Demo

With devyard:

```bash
devyard run install
devyard run build
devyard up -d
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

This repository includes `.github/workflows/publish.yml` for PyPI Trusted Publishing.

Recommended release flow:

1. Update `version` in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Run the packaging checks above.
4. Create a GitHub release or trigger the publish workflow manually.
5. Configure the PyPI project trusted publisher for `yangsengui/fastapi-openapi-agent` before the first automated release.

Manual upload is also possible:

```bash
python -m twine upload dist/*
```

## License

MIT. See `LICENSE`.
