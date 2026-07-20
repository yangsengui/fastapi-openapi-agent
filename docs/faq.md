# 常见问题

## 它会读取哪一份 OpenAPI？

FastAPI adapter 在每次聊天运行时读取 `app.openapi()`。`/_agent/openapi` 可用于检查 Agent 实际看到的快照。

## 必须配置 LLM 吗？

不是。无模型时可以用内置确定性 responder 做接口检索与本地联调。要获得自然语言规划、多轮工具调用和结果总结，需要配置支持工具调用的模型。

## 支持哪些模型？

项目通过 LiteLLM 接入模型提供方，包括 OpenAI、DeepSeek、Anthropic、Gemini、Azure、OpenRouter、Ollama 和 OpenAI-compatible gateway。具体能力取决于所选模型；请选择支持 tool calling 的型号。

## OpenAPI 很大怎么办？

初始上下文只放精简操作元数据，完整请求、响应和组件 Schema 在选中操作后按需加载。目录超出限制时会进一步通过 `operation_search` 缩小范围。

## 为什么 Agent 选错接口？

优先检查：

1. 是否有唯一、稳定且语义明确的 `operationId`；
2. `summary` 是否表达“动作 + 业务对象”；
3. `description` 和 `tags` 是否能区分相似操作；
4. 参数和 Schema 是否有业务含义说明；
5. 是否存在多个几乎同义但边界不清的操作。

参见 [OpenAPI 质量指南](guides/openapi-quality.md)。

## 会直接执行 POST 或 DELETE 吗？

默认不会。只有 `GET`、`HEAD`、`OPTIONS` 被视为只读。其他 method 需要 `allow_mutating_api_calls=True`，并且仍应由宿主 API 完成认证、授权和参数校验。

## API 调用会经过公网吗？

FastAPI adapter 通过 ASGI 在进程内调用宿主应用，不需要公网往返。模型请求仍会发往你配置的模型提供方或网关。

## 如何让 Agent 使用当前用户身份？

用 `forward_headers` 配置服务端透传白名单，或在前端通过 `window.OpenAgent.request` 复用现有认证请求层。宿主 API 必须继续进行完整授权。

## 能否完全替换默认 Agent？

可以。传入自定义 `responder`，或用 `AgentBackend`、`AgentContext`、`OpenAPIAgent` 构建自定义 backend，同时复用操作目录、运行时工具和标准 HTTP/SSE 协议。

## 如何切换文档语言？

使用站点顶部的语言选择器。中文位于站点根路径，英文位于 `/en/`；如果当前页面有对应翻译，切换时会停留在同一页面。
