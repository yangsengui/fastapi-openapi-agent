# OpenAPI 如何变成 Agent

OpenAgent 不会在启动时把整份 OpenAPI 原样塞给模型，而是使用“发现 → 取契约 → 执行”的渐进流程。

```text
FastAPI app.openapi()
        │
        ▼
OperationCatalog（精简元数据）
        │ operation_search
        ▼
候选 operationId
        │ operation_get
        ▼
完整参数、请求体、响应与引用 Schema
        │ operation_request
        ▼
ASGI 进程内调用宿主 API
        │
        ▼
基于真实结果生成回答
```

## 第一步：操作发现

目录保留每个操作的：

- HTTP method 和 path；
- `operationId`；
- `summary`、`description`、`tags`；
- 参数名、是否有 request body、响应状态码。

请求和响应的完整 Schema 不在初始目录里。对大型 API，这能显著减少上下文占用。若目录仍超过 `max_context_chars`，模型会使用 `operation_search` 进一步筛选。

## 第二步：精确读取契约

模型选中操作后必须先调用 `operation_get`。运行时会合并 path-level 与 operation-level 参数，并递归收集当前操作引用的 `components.schemas`。

这一步让模型基于准确契约填写 path、query、header 和 body，而不是凭接口名称猜参数。

## 第三步：受控执行

只有已经在当前运行中通过 `operation_get` 加载过的操作才能进入 `operation_request`。FastAPI adapter 使用 `httpx.ASGITransport` 在进程内调用宿主应用，并可透传白名单中的请求头。

默认规则：

- `GET`、`HEAD`、`OPTIONS` 被视为 `read_only`；
- 其他 method 被视为 `mutating`；
- `mutating` 操作只有在 `allow_mutating_api_calls=True` 时才可执行；
- Agent 自己的路由不能被 Agent 再次调用。

可用 `x-acp-operation.risk` 覆盖风险分类：

```yaml
paths:
  /reports/preview:
    post:
      operationId: preview_report
      x-acp-operation:
        risk: read_only
```

只有真实无副作用的操作才应标为 `read_only`。

## 两种运行模式

| 模式 | 能做什么 | 适合场景 |
| --- | --- | --- |
| 内置 responder | 离线搜索、列出与解释接口 | 本地开发、验证 OpenAPI、无外部请求环境 |
| LiteLLM Agent | 多轮工具选择、读取契约、调用 API、总结结果 | 面向用户的自然语言操作与业务问答 |

## 设计原则

OpenAPI 是唯一接口事实来源；模型负责计划和表达，运行时负责契约、权限和调用约束。这样可以独立替换模型，而不需要重新定义每一个 API 工具。
