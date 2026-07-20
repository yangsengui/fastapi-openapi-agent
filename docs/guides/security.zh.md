# 认证与安全

Agent 会把自然语言意图转化为 API 调用，因此应把它视为一个真实 API 客户端，而不是单纯聊天组件。

## 两层认证

需要分别处理：

1. **保护 Agent 路由**：谁可以访问 `/_agent/`、`/_agent/chat` 和 OpenAPI 快照。
2. **Agent 调用宿主 API 的身份**：进程内请求应代表当前用户，而不是无条件使用服务账号。

OpenAgent 不替代宿主应用的认证与授权。应使用现有 FastAPI middleware、受保护 router 或反向代理保护 Agent 路由。

## 透传当前用户身份

```python
install_openapi_agent(
    app,
    forward_headers=("authorization", "cookie", "x-tenant-id"),
    allow_mutating_api_calls=False,
)
```

只把确实需要的 header 加入白名单。宿主 API 必须再次校验 token、租户边界和资源级权限。

## 写操作策略

默认只允许 `GET`、`HEAD`、`OPTIONS`。要允许其他 method，必须显式开启：

```python
install_openapi_agent(app, allow_mutating_api_calls=True)
```

上线写操作前建议同时具备：

- 清晰的操作副作用描述和稳定 `operationId`；
- 终端用户确认机制；
- 幂等键或服务端防重；
- 资源级授权；
- 调用人、参数摘要、操作结果的审计日志；
- 对金额、数量和批量范围的服务端限制；
- 超时、撤销或补偿策略。

!!! warning

    `allow_mutating_api_calls=True` 是应用级开关，不是用户确认流程。当前版本不会自动弹出逐次审批 UI；高风险操作应通过自定义 Agent backend 或业务接口实现额外审批。

## OpenAPI 暴露

默认提供 `/_agent/openapi`。若 Schema 包含不应向当前访问者公开的内部操作，可关闭快照：

```python
install_openapi_agent(app, expose_openapi=False)
```

但这只关闭快照路由；Agent 运行时仍使用 `app.openapi()`。如果不同用户应看到不同能力，需要在 OpenAPI 生成、Agent 路由或自定义 backend 中实现相应隔离。

## 模型与数据边界

- 确认所选模型供应商的数据保留和训练策略；
- 不在 descriptions、examples 或默认值中放真实密钥与个人数据；
- 对工具返回值进行业务级最小化；
- 自定义 Agent 可在发给模型前脱敏；
- 对 prompt injection 按“不信任 API 数据内容”的原则处理；
- 服务端授权必须是最终安全边界，不能依赖模型自觉。

## 生产检查清单

- [ ] Agent 页面、聊天接口和 OpenAPI 快照都在认证之后。
- [ ] `forward_headers` 是最小白名单。
- [ ] 所有宿主操作执行资源级授权。
- [ ] 写操作默认关闭，或具备确认、审计和防重机制。
- [ ] 模型 key 由 secret manager 管理。
- [ ] 日志不记录 token、cookie 和敏感请求体。
- [ ] API 调用有速率限制、超时与响应大小限制。
- [ ] OpenAPI 没有暴露内部或管理操作。
