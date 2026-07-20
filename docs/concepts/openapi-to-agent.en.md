# How OpenAPI becomes an Agent

OpenAgent does not send the entire OpenAPI document to the model at startup. It uses a progressive **discover → load contract → execute** workflow.

```text
FastAPI app.openapi()
        │
        ▼
OperationCatalog (compact metadata)
        │ operation_search
        ▼
Candidate operationId
        │ operation_get
        ▼
Exact parameters, request body, responses, and referenced schemas
        │ operation_request
        ▼
In-process ASGI request to the host API
        │
        ▼
Answer grounded in the real response
```

## Step 1: discover operations

The catalog retains only the information needed to identify each operation:

- HTTP method and path;
- `operationId`;
- `summary`, `description`, and `tags`;
- parameter names, request-body presence, and response status codes.

Full request and response schemas are excluded from the initial catalog. This reduces context usage for large APIs. If the catalog still exceeds `max_context_chars`, the model uses `operation_search` to narrow the candidates.

## Step 2: load the exact contract

After selecting an operation, the model must call `operation_get`. The runtime merges path-level and operation-level parameters and recursively collects the referenced `components.schemas` for that operation.

The model can then fill path, query, header, and body values from the real contract instead of guessing from the endpoint name.

## Step 3: execute under policy

Only an operation loaded through `operation_get` during the current run can be passed to `operation_request`. The FastAPI adapter uses `httpx.ASGITransport` to call the host app in-process and may forward an allowlist of request headers.

Default policy:

- `GET`, `HEAD`, and `OPTIONS` are classified as `read_only`;
- all other methods are classified as `mutating`;
- mutating operations require `allow_mutating_api_calls=True`;
- the Agent cannot call its own internal routes.

You can override the risk classification with `x-acp-operation.risk`:

```yaml
paths:
  /reports/preview:
    post:
      operationId: preview_report
      x-acp-operation:
        risk: read_only
```

Only operations that are genuinely side-effect free should be marked `read_only`.

## Two runtime modes

| Mode | Capabilities | Best for |
| --- | --- | --- |
| Built-in responder | Offline operation search, listing, and contract explanation | Local development, OpenAPI validation, environments without external requests |
| LiteLLM Agent | Multi-step tool selection, contract loading, API execution, and result synthesis | User-facing natural-language workflows and business questions |

## Design principle

OpenAPI is the single source of truth for the interface. The model plans and explains; the runtime enforces contracts, permissions, and execution constraints. Models can therefore be replaced without redefining every API tool.
