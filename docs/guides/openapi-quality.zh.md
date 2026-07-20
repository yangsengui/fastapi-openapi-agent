# OpenAPI 质量指南

高质量 OpenAPI 不是“能打开 Swagger UI”就够了。对 Agent 来说，它同时承担工具目录、参数说明、返回值契约和风险提示的职责。

## Agent 最关心的字段

| 优先级 | 字段 | 作用 | 建议 |
| --- | --- | --- | --- |
| P0 | `operationId` | 稳定选择并调用操作 | 全局唯一、长期稳定、使用动词加业务对象 |
| P0 | 参数与 request body Schema | 正确生成调用输入 | 标明 required、类型、约束、格式和字段说明 |
| P0 | responses | 理解成功与失败结果 | 至少覆盖主要成功响应和常见 4xx |
| P1 | `summary` | 快速匹配用户意图 | 用“动作 + 对象”，不要写成泛化的“处理请求” |
| P1 | `description` | 补充业务前置条件和边界 | 写清可见范围、副作用、状态限制和分页语义 |
| P1 | `tags` | 缩小业务域 | 使用稳定的领域名，不按团队临时命名 |
| P1 | Schema 字段 description | 正确填写枚举、ID、时间和金额 | 描述业务含义，不重复字段名 |
| P2 | examples | 帮助模型理解格式 | 示例必须可通过当前 Schema 校验 |
| P2 | security | 表达认证方式与 scope | 文档与实际中间件保持一致 |

## 推荐命名

好的 `operationId`：

```text
list_inventory_items
get_inventory_item
create_inventory_item
cancel_purchase_order
preview_monthly_report
```

不推荐：

```text
items_get
handle_request
api_v2_action
postData
```

不要把 URL 版本或框架自动生成的细节当成长期工具名。修改 path 时，稳定的 `operationId` 能减少 Agent 行为漂移。

## 一个完整的 FastAPI 示例

```python
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class OrderSummary(BaseModel):
    id: str = Field(description="订单 ID", example="ord_01JABC")
    status: OrderStatus = Field(description="订单当前状态")
    total_cents: int = Field(ge=0, description="以分为单位的订单总额", example=12900)


app = FastAPI(
    title="Orders API",
    version="1.0.0",
    description="查询和管理当前租户的订单。所有时间均使用 RFC 3339 UTC。",
)


@app.get(
    "/orders",
    operation_id="list_orders",
    summary="查询订单",
    description="返回当前租户可见的订单，按创建时间倒序排列。",
    tags=["orders"],
    response_model=List[OrderSummary],
    responses={
        401: {"description": "访问令牌缺失或无效"},
        403: {"description": "调用者不能访问该租户"},
    },
)
def list_orders(
    tenant_id: str = Header(description="租户 ID", example="tenant_demo"),
    status: Optional[OrderStatus] = Query(default=None, description="按订单状态过滤"),
    limit: int = Query(default=20, ge=1, le=100, description="最多返回的订单数"),
) -> List[OrderSummary]:
    return []
```

## 风险元数据

OpenAgent 默认按 HTTP method 判断风险。若一个 `POST` 只是预览且绝对无副作用，可以显式标记：

```python
@app.post(
    "/reports/preview",
    operation_id="preview_report",
    openapi_extra={"x-acp-operation": {"risk": "read_only"}},
)
def preview_report(payload: ReportRequest) -> ReportPreview:
    ...
```

!!! danger

    不要为了绕过写操作保护而错误标记风险。任何可能创建资源、发消息、扣款、改变状态或触发异步任务的操作都应保持 `mutating`。

## 发布前检查清单

- [ ] 每个可供 Agent 使用的操作都有唯一且稳定的 `operationId`。
- [ ] `summary` 能脱离 path 单独表达业务动作。
- [ ] `description` 写清前置条件、副作用、可见范围与分页规则。
- [ ] 所有 path 参数都标记为 required，类型与真实路由一致。
- [ ] ID、金额、日期、时区、枚举和单位都有明确说明。
- [ ] request body 的必填字段、嵌套对象和约束完整。
- [ ] 成功响应有具体 Schema，常见错误有状态码和含义。
- [ ] examples 能通过 Schema 校验且不包含真实敏感数据。
- [ ] security scheme、scope 与生产认证策略一致。
- [ ] 写操作没有被错误标记为 `read_only`。
- [ ] 用 `/_agent/openapi` 检查的是运行时最终 Schema，而非一份过期文件。

## 如何验收 Agent 效果

为每个核心操作准备三类测试问题：

1. **明确问题**：直接说出业务动作，应该一次选中正确操作。
2. **口语问题**：使用用户真实表达，仍应匹配正确 `operationId`。
3. **歧义问题**：缺少必填参数时，Agent 应询问或明确指出缺失信息，不应猜测。

建议将这些问题和期望操作记录为回归样例。OpenAPI 变更、模型升级或 prompt 调整后重复执行。
