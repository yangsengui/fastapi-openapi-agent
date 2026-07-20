# HTTP and SSE protocols

The following routes use `/_agent` by default. Changing `path` changes the prefix consistently.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Standalone Agent page |
| GET | `/widget/` | Widget SPA |
| GET | `/sidebar.js` | Embeddable loader |
| GET | `/config` | UI and capability configuration |
| GET | `/openapi` | Optional host OpenAPI snapshot |
| POST | `/chat` | JSON chat endpoint |
| POST | `/chat/stream` | SSE streaming chat endpoint |

## JSON request

```http
POST /_agent/chat
Content-Type: application/json

{
  "message": "List inventory owned by the network team",
  "context": {
    "language": "en"
  }
}
```

`context.language` may select `en` or `zh` for an individual request.

## JSON response

```json
{
  "answer": "...",
  "operations": [],
  "sources": [],
  "tool_results": []
}
```

Exact content depends on the responder. `tool_results` can be used to audit tool names, inputs, statuses, and previews.

## SSE events

`POST /_agent/chat/stream` returns `text/event-stream`. Common event types:

| type | Meaning |
| --- | --- |
| `start` | Agent run started |
| `text-start` | A text part started |
| `text-delta` | Incremental text |
| `text-end` | A text part ended |
| `tool-input-start` | Tool argument generation started |
| `tool-input-available` | Complete tool input is available |
| `tool-output-available` | Tool execution succeeded |
| `tool-output-error` | Tool returned a failure |
| `error` | Run error |
| `finish` | Run completed with the final response |

Each event is sent as an SSE `data:` line. The stream terminates with:

```text
data: [DONE]
```

Clients must support multiple text parts and tool calls in one answer rather than assuming each event type appears only once.
