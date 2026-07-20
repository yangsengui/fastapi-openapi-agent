# 配置与模型

## FastAPI 配置

```python
from openagent.fastapi import OpenAPIAgentConfig, install_openapi_agent

config = OpenAPIAgentConfig(
    path="/_agent",
    title="Orders Agent",
    welcome_title="需要查询什么订单？",
    description="可以查询订单、解释接口，并在授权范围内调用 API。",
    language="zh",
    expose_openapi=True,
    enable_api_calls=True,
    allow_mutating_api_calls=False,
    forward_headers=("authorization", "cookie"),
)

install_openapi_agent(app, config)
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `path` | `/_agent` | Agent 路由前缀 |
| `title` | `OpenAgent` | 页面与 Widget 标题 |
| `welcome_title` | `None` | 首屏欢迎标题 |
| `description` | 内置文案 | 能力边界说明 |
| `language` | `en` | `en` 或 `zh`，同时影响 UI 与模型指令 |
| `include_in_schema` | `False` | 是否把 Agent 自身路由加入宿主 OpenAPI |
| `expose_openapi` | `True` | 是否提供 `{path}/openapi` 快照 |
| `enable_api_calls` | `True` | 是否允许调用宿主 API |
| `allow_mutating_api_calls` | `False` | 是否允许非只读操作 |
| `auto_llm` | `True` | 有模型配置时自动启用 LiteLLM |
| `forward_headers` | authorization、cookie | 进程内调用时透传的请求头白名单 |

关键字参数也可直接传入，适合短配置：

```python
install_openapi_agent(
    app,
    path="/api-agent",
    language="zh",
    allow_mutating_api_calls=False,
)
```

## 模型环境变量

| 变量 | 作用 |
| --- | --- |
| `OPENAGENT_MODEL` | LiteLLM 模型名，如 `openai/gpt-4o-mini` |
| `OPENAGENT_API_KEY` | 通用或网关 API key |
| `OPENAGENT_BASE_URL` | OpenAI-compatible 网关地址 |
| 提供商自己的变量 | 如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` |

也可以在代码中设置：

```python
install_openapi_agent(
    app,
    llm_model="openai/my-model",
    llm_api_key="gateway-key",
    llm_base_url="https://gateway.example.com/v1",
    llm_model_kwargs={"num_retries": 2},
)
```

生产环境不要把密钥写进源码。优先使用 secret manager 或部署平台的加密环境变量。

## 大型 API

LiteLLM responder 的初始操作目录受 `max_context_chars` 控制，完整操作契约始终按需加载。自定义 responder 时可调整：

```python
from openagent import create_llm_responder

responder = create_llm_responder(
    model="openai/my-model",
    max_context_chars=24000,
    max_tool_rounds=6,
    timeout=45,
)
```

显式创建的 responder 没有宿主 FastAPI invoker，因此只能搜索和读取契约。需要执行真实 API 时，使用自动 LLM 集成，或通过 SDK 提供自定义 Agent backend。

## 自定义 responder

```python
from openagent import AgentRequest, AgentResponse


async def responder(request: AgentRequest, openapi: dict) -> AgentResponse:
    return AgentResponse(answer="由内部 Agent 平台生成的回答")


install_openapi_agent(app, responder=responder)
```

`agent` 与 `responder` 不能同时配置。
