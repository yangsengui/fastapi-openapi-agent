# Python API

## `install_openapi_agent`

```python
from openagent.fastapi import install_openapi_agent

router = install_openapi_agent(app, config=None, **overrides)
```

把 Agent router 加到现有 FastAPI app，并返回该 `APIRouter`。可传入 `OpenAPIAgentConfig`，也可使用关键字覆盖配置。

## `OpenAPIAgentConfig`

配置项及默认值以 [`src/openagent/fastapi.py`](https://github.com/yangsengui/fastapi-openapi-agent/blob/main/src/openagent/fastapi.py) 为准。常用项见[配置与模型](../guides/configuration.md)。

## `OperationCatalog`

在不依赖 FastAPI 的情况下搜索 OpenAPI：

```python
from openagent import OperationCatalog

catalog = OperationCatalog.from_openapi(openapi_document)
all_operations = catalog.list_operations()
matches = catalog.search_operations("创建用户", method="POST", limit=5)
contract = catalog.require_operation("create_user")
```

`OperationMetadata` 只包含精简检索信息；`OperationContract` 包含选中操作、风险分类和引用的组件 Schema。

## `OpenAPIAgentRuntime`

运行时提供三个标准工具：

| 工具 | 作用 |
| --- | --- |
| `operation_search` | 按自然语言、method 或 operationId 搜索操作 |
| `operation_get` | 加载选中操作的精确契约 |
| `operation_request` | 在策略允许时执行已经加载的操作 |

框架无关用法：

```python
from openagent import OpenAPIAgentRuntime

runtime = OpenAPIAgentRuntime(openapi_document, enable_api_calls=False)
result = runtime.operation_search({"query": "查询订单"})
```

要调用真实 API，adapter 必须提供实现 `OperationInvoker` 协议的 invoker。

## 自定义 Agent SDK

```python
from openagent import AgentBackend, AgentContext, AgentResponse, OpenAPIAgent


class MyBackend(AgentBackend):
    async def respond(self, context: AgentContext) -> AgentResponse:
        matches = context.catalog.search_operations(context.request.message, limit=1)
        if not matches:
            return AgentResponse(answer="没有找到匹配的操作。")

        selected = matches[0]
        contract = await context.run_tool(
            "operation_get",
            {"operationId": selected.operation_id},
        )
        return AgentResponse(answer=contract["preview"])


agent = OpenAPIAgent(MyBackend())
install_openapi_agent(app, agent=agent)
```

只实现 `respond` 即可获得标准 SSE 事件序列。需要真正逐 token 输出时，覆盖 `stream` 并产生 `TextDeltaEvent`、`ToolInputAvailableEvent`、`ToolOutputAvailableEvent` 等类型事件。

## LiteLLM helper

```python
from openagent import create_llm_responder, stream_llm_agent
```

`create_llm_responder` 创建 JSON responder；`stream_llm_agent` 产生 UI 可消费的流式事件。两者都需要 `llm` 可选依赖。
