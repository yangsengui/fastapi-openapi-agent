# 嵌入式 API Agent 还是 MCP Server？

如果你已经有一个 FastAPI 应用，它的 OpenAPI 文档通常已经描述了 AI
系统调用 API 所需的大部分信息：operation ID、参数、请求体、响应 Schema
和接口说明。

因此，一个自然的思路是：直接复用现有 API 契约，不再维护第二套 Agent
工具定义。

但这个思路实际上包含两种不同的产品形态：

1. 把 FastAPI 应用暴露为外部 MCP 客户端可以发现和调用的工具；
2. 把自然语言 API 操作界面直接放进现有应用。

它们都可以复用 OpenAPI，但解决的集成问题并不相同。

## 什么情况下适合 MCP Server

如果用户已经在使用支持 MCP 的客户端，并希望客户端把你的 API 当成一组
工具进行发现和调用，那么 MCP Server 是更自然的形态。

此时，主要边界位于外部客户端和 MCP Server 之间。需要重点考虑传输协议、
会话、客户端兼容性、鉴权，以及 API operation 如何映射为 MCP 工具。

它适合需要让多个兼容客户端使用的开发者工具和 API 服务。

## 什么情况下适合嵌入式 API Agent

如果自然语言入口本身属于你的产品，则更适合嵌入式 Agent，例如：

- 内部运营后台中的助手；
- 管理 API 的自然语言操作入口；
- SaaS 产品内的 API-aware Widget；
- 需要复用当前用户身份和租户上下文的受控界面。

在这种情况下，你同时拥有宿主 API 和用户体验，核心问题会变成：

- 助手 UI 放在哪里？
- 如何复用当前用户的鉴权和租户上下文？
- Agent 可以调用哪些 API operation？
- 是否能在不增加一次公网请求的情况下调用宿主 API？
- 如何先从只读权限开始，再谨慎考虑写操作？

## 让 OpenAPI 继续作为事实来源

假设应用已经定义了库存查询接口：

```python
from typing import Optional

from fastapi import FastAPI, Query

app = FastAPI(title="Inventory API")


@app.get(
    "/items",
    operation_id="list_inventory_items",
    summary="List inventory items",
    description="Return inventory items, optionally filtered by owner.",
)
def list_items(
    owner: Optional[str] = Query(
        default=None,
        description="Return only inventory items owned by this team.",
    ),
):
    ...
```

如果再手写一份工具定义，就会重复维护 operation 名称、参数类型、参数说明和
接口行为。当 API 发生变化，两份定义很容易失去同步。

OpenAPI-native 集成直接读取运行中应用生成的契约。

这不意味着每次都把完整 OpenAPI 文档发送给模型。OpenAgent 使用渐进流程：

```text
发现 operation
→ 选择可能匹配的 operation
→ 加载精确契约
→ 校验并执行调用
```

模型先看到精简元数据，只在确定候选 operation 后加载详细请求和响应 Schema。

## 最小嵌入示例

OpenAgent 是一个处于 alpha 阶段的开源项目，用于探索 FastAPI 和 Django
Ninja 的嵌入式 API Agent 形态。

安装 FastAPI 适配：

```bash
pip install "fastapi-openapi-agent[fastapi]"
```

安装到现有应用：

```python
from fastapi import FastAPI
from openagent.fastapi import install_openapi_agent

app = FastAPI(title="My API")
install_openapi_agent(app)
```

应用会在 `/_agent/` 提供独立助手页面，同时提供可嵌入 Widget。运行时使用
宿主应用的 OpenAPI 文档，并可通过 ASGI 在进程内执行允许的 operation。

## 从有限的执行边界开始

自然语言不能代替鉴权。宿主 API 仍然必须验证调用者身份，并执行资源级权限
检查。

OpenAgent 默认允许 `GET`、`HEAD` 和 `OPTIONS`，写操作需要显式开启。
这只是起始边界，不是一套完整的审批系统。

启用写操作之前，应用可能还需要：

- operation 级策略；
- 明确的用户确认；
- 幂等键或服务端去重；
- 审计日志；
- 资源级鉴权；
- 金额、数量和批量大小限制；
- 失败后的恢复或补偿机制。

OpenAgent 当前的写操作开关是应用级配置，不会自动生成逐次调用审批界面。

## 选择参考

| 问题 | MCP Server | 嵌入式 API Agent |
| --- | --- | --- |
| 主要用户界面 | 外部 MCP 客户端 | 你的应用 |
| 主要集成边界 | 客户端 ↔ MCP Server | 助手 ↔ 宿主应用 |
| UI 归属 | 通常由客户端提供 | 可以由应用提供 |
| 用户上下文 | 由外部客户端或集成层提供 | 可以复用宿主页面和请求上下文 |
| 适合的第一场景 | 让兼容客户端使用 API 工具 | 给现有产品增加 API 助手 |

两种方式并不互斥。成熟 API 产品最终可能同时提供两种入口。第一个值得回答的
问题不是“哪个协议会赢”，而是：

> 用户应该在哪里操作 API，以及谁拥有这个交互体验？

如果答案是“现有 FastAPI 或 Django Ninja 产品内部”，可以继续阅读
[5 分钟开始](../getting-started.md)。
