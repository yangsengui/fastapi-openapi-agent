# Frequently asked questions

## Which OpenAPI document does OpenAgent use?

The FastAPI adapter reads `app.openapi()` for every chat run. Inspect `/_agent/openapi` to see the exact snapshot available to the Agent.

## Is an LLM required?

No. The built-in deterministic responder supports operation search and local integration testing without a model. Natural-language planning, multi-step tool use, and response synthesis require a configured tool-calling model.

## Which models are supported?

LiteLLM provides access to OpenAI, DeepSeek, Anthropic, Gemini, Azure, OpenRouter, Ollama, and OpenAI-compatible gateways. Exact capabilities depend on the selected model; choose one that supports tool calling.

## What if my OpenAPI document is large?

The initial context contains compact operation metadata only. Full request, response, and component schemas are loaded after an operation is selected. If the catalog exceeds the configured limit, `operation_search` narrows it further.

## Why did the Agent select the wrong endpoint?

Check these fields first:

1. Is `operationId` unique, stable, and meaningful?
2. Does `summary` clearly state the action and business object?
3. Do `description` and `tags` distinguish similar operations?
4. Do parameters and schema fields explain their business meaning?
5. Are there nearly synonymous operations with unclear boundaries?

See the [OpenAPI quality guide](guides/openapi-quality.md).

## Will it execute POST or DELETE automatically?

Not by default. Only `GET`, `HEAD`, and `OPTIONS` are considered read-only. Other methods require `allow_mutating_api_calls=True`, and the host API must still enforce authentication, authorization, and validation.

## Do API calls leave the process?

The FastAPI adapter calls the host application in-process through ASGI, so no public HTTP round trip is required. Model requests still go to the configured provider or gateway.

## How does the Agent use the current user's identity?

Configure a server-side `forward_headers` allowlist or reuse the frontend authentication layer through `window.OpenAgent.request`. The host API must continue to perform full authorization.

## Can I replace the default Agent?

Yes. Supply a custom `responder`, or build a backend with `AgentBackend`, `AgentContext`, and `OpenAPIAgent` while reusing the operation catalog, runtime tools, and standard HTTP/SSE protocol.

## How do I switch documentation languages?

Use the language selector in the site header. English is served from the site root and Chinese from `/zh/`. The selector keeps you on the equivalent page when a translation exists.
