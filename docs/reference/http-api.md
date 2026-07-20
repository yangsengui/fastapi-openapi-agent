# HTTP 与 SSE 协议

以下路由默认挂载在 `/_agent`；修改 `path` 后前缀会同步变化。

| Method | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 独立 Agent 页面 |
| GET | `/widget/` | Widget SPA |
| GET | `/sidebar.js` | 可嵌入 loader |
| GET | `/config` | UI 与能力配置 |
| GET | `/openapi` | 宿主 OpenAPI 快照，可关闭 |
| POST | `/chat` | JSON 聊天接口 |
| POST | `/chat/stream` | SSE 流式聊天接口 |

## JSON 请求

```http
POST /_agent/chat
Content-Type: application/json

{
  "message": "查询 network 团队的库存",
  "context": {
    "language": "zh"
  }
}
```

`context.language` 可为单次请求选择 `en` 或 `zh`。

## JSON 响应

```json
{
  "answer": "……",
  "operations": [],
  "sources": [],
  "tool_results": []
}
```

字段内容取决于 responder。`tool_results` 可用于审计工具名称、输入、状态和预览信息。

## SSE 事件

`POST /_agent/chat/stream` 返回 `text/event-stream`。常见事件类型：

| type | 含义 |
| --- | --- |
| `start` | Agent 运行开始 |
| `text-start` | 一段文本开始 |
| `text-delta` | 文本增量 |
| `text-end` | 一段文本结束 |
| `tool-input-start` | 工具参数生成开始 |
| `tool-input-available` | 完整工具输入可用 |
| `tool-output-available` | 工具执行成功 |
| `tool-output-error` | 工具返回失败 |
| `error` | 运行错误 |
| `finish` | 运行完成并携带最终响应 |

每条消息使用 SSE `data:` 行发送，流结束时还会发送：

```text
data: [DONE]
```

前端应容忍同一回答包含多个 text part 与多个 tool call，不要假设事件只出现一次。
