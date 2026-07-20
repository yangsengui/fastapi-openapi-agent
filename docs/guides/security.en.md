# Authentication and security

An Agent converts natural-language intent into API calls. Treat it as a real API client, not merely a chat component.

## Two authentication layers

Handle these concerns separately:

1. **Protect Agent routes:** decide who may access `/_agent/`, `/_agent/chat`, and the OpenAPI snapshot.
2. **Represent the caller:** in-process requests should act as the current user, not as an unrestricted service account.

OpenAgent does not replace authentication or authorization in the host application. Protect the Agent routes with your existing FastAPI middleware, protected router, or reverse proxy.

## Forward the caller identity

```python
install_openapi_agent(
    app,
    forward_headers=("authorization", "cookie", "x-tenant-id"),
    allow_mutating_api_calls=False,
)
```

Keep this allowlist minimal. The host API must validate the token, tenant boundary, and resource-level permissions again.

## Mutating-operation policy

Only `GET`, `HEAD`, and `OPTIONS` are allowed by default. Other methods require explicit opt-in:

```python
install_openapi_agent(app, allow_mutating_api_calls=True)
```

Before enabling writes, add:

- stable operation IDs and explicit side-effect descriptions;
- end-user confirmation for consequential actions;
- idempotency keys or server-side deduplication;
- resource-level authorization;
- audit logs for caller, argument summary, and result;
- server-side limits for amounts, quantities, and batch size;
- timeout, cancellation, or compensation strategies.

!!! warning

    `allow_mutating_api_calls=True` is an application-level switch, not a user approval flow. The current version does not automatically display per-call approval prompts. High-risk operations should add approval in a custom Agent backend or in the business API itself.

## OpenAPI exposure

`/_agent/openapi` is enabled by default. Disable the snapshot route if the schema includes operations that should not be visible to the current caller:

```python
install_openapi_agent(app, expose_openapi=False)
```

This only disables the snapshot route; the Agent still uses `app.openapi()` at runtime. If different users should receive different capabilities, implement the boundary in OpenAPI generation, Agent routing, or a custom backend.

## Model and data boundaries

- Review the retention and training policies of the selected model provider.
- Keep real secrets and personal data out of descriptions, examples, and defaults.
- Minimize tool responses at the business layer.
- Redact sensitive values before sending them to the model in a custom Agent.
- Treat API response content as untrusted with respect to prompt injection.
- Keep server-side authorization as the final security boundary; never depend on model behavior.

## Production checklist

- [ ] Agent pages, chat routes, and OpenAPI snapshots require authentication.
- [ ] `forward_headers` is a minimal allowlist.
- [ ] Every host operation performs resource-level authorization.
- [ ] Writes are disabled or protected with confirmation, auditing, and deduplication.
- [ ] Model keys are managed through a secret manager.
- [ ] Logs exclude tokens, cookies, and sensitive request bodies.
- [ ] Calls have rate limits, timeouts, and response-size limits.
- [ ] Internal and administrative operations are excluded from the exposed OpenAPI document.
