# 让 OpenAPI 不止是一份接口文档

OpenAgent 是一个 **OpenAPI-native API Agent**：它把已有 FastAPI 应用的 OpenAPI 定义变成一个可对话、可检索接口契约，并可在授权范围内调用真实 API 的 Agent。

```python
from openagent.fastapi import install_openapi_agent

install_openapi_agent(app, language="zh")
```

这一行会为应用挂载 Agent 页面、聊天接口、SSE 流式输出、OpenAPI 快照和可嵌入侧边栏。打开 `/_agent/` 即可使用。

## 为什么从 OpenAPI 生成 Agent

传统 API Agent 往往需要再次手写工具名称、参数和说明。这会产生两份事实来源，也容易在接口变更后失效。OpenAgent 直接使用应用运行时生成的 OpenAPI：

- `operationId` 成为稳定的工具身份；
- `summary`、`description` 和 `tags` 帮助 Agent 找到正确操作；
- 参数、请求体、响应和组件 Schema 在调用前按需加载；
- 安全配置决定哪些身份信息可透传；
- 只读与写操作有不同的默认执行策略。

因此，**Agent 的上限首先由 OpenAPI 的质量决定**。项目提供的不只是挂载组件，也是一条“接口定义即 Agent 能力”的工程路径。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 一行接入 | 对现有 FastAPI 应用调用 `install_openapi_agent(app)` |
| 契约驱动 | 从 `app.openapi()` 构建操作目录，不维护重复工具定义 |
| 渐进加载 | 先给模型精简目录，选中操作后再加载完整 Schema |
| 安全执行 | 默认仅允许 `GET`、`HEAD`、`OPTIONS`，写操作需显式开启 |
| 进程内调用 | 通过 ASGI 直接调用宿主 API，无需绕行公网 |
| 模型中立 | 通过 LiteLLM 接入 OpenAI、DeepSeek、Anthropic、Gemini 等提供方 |
| 可嵌入 UI | 提供独立页面、iframe Widget 和浮动侧边栏 |
| 可扩展 SDK | 可替换模型、策略层或整个 Agent backend |

## 最短路径

1. 写好或改善 FastAPI 接口的 OpenAPI 元数据。
2. 安装 `fastapi-openapi-agent[fastapi,llm]`。
3. 配置一个支持工具调用的模型。
4. 调用 `install_openapi_agent(app)`。
5. 先以只读模式验证，再按业务需要开启写操作。

[开始构建第一个 Agent](getting-started.md){ .md-button .md-button--primary }
[查看 OpenAPI 质量指南](guides/openapi-quality.md){ .md-button }

## 当前状态

项目处于 Alpha 阶段，公开 API 在首个稳定版前可能调整。生产环境请固定版本，并重点审查认证透传、写操作权限和模型供应商的数据策略。
