# 5 分钟生成第一个 API Agent

本页从一个现有 FastAPI 应用出发，用一行 Python 接入 OpenAgent。

## 1. 安装

=== "带 LLM"

    ```bash
    pip install "fastapi-openapi-agent[fastapi,llm]"
    ```

=== "仅本地能力"

    ```bash
    pip install "fastapi-openapi-agent[fastapi]"
    ```

不配置模型时，内置确定性 responder 仍可用于接口搜索和本地联调，但不会具备完整的自然语言推理能力。

## 2. 准备一个高质量接口

```python title="app.py"
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int = Field(description="库存项的唯一 ID", example=42)
    name: str = Field(description="可展示的库存名称", example="路由器")
    owner: str = Field(description="负责团队", example="network")


app = FastAPI(
    title="Inventory API",
    version="1.0.0",
    description="查询和管理组织内的库存资产。",
)


@app.get(
    "/items",
    operation_id="list_inventory_items",
    summary="查询库存项",
    description="返回当前调用者有权查看的库存项，可按负责团队过滤。",
    tags=["inventory"],
    response_model=List[Item],
    responses={401: {"description": "调用者未登录"}},
)
def list_items(
    owner: Optional[str] = Query(
        default=None,
        description="只返回该团队负责的库存项",
        example="network",
    ),
) -> List[Item]:
    return [Item(id=42, name="路由器", owner=owner or "network")]
```

`operation_id`、动作明确的 `summary`、业务约束完整的 `description`，以及字段描述会直接提升 Agent 选工具和填参数的稳定性。

## 3. 一行挂载 Agent

在同一文件末尾加入：

```python
from openagent.fastapi import install_openapi_agent

install_openapi_agent(app, language="zh")
```

## 4. 配置模型

选择一个支持工具调用的模型。下面只需配置其中一组：

=== "OpenAI"

    ```bash
    export OPENAGENT_MODEL="openai/gpt-4o-mini"
    export OPENAI_API_KEY="your-api-key"
    ```

=== "DeepSeek"

    ```bash
    export OPENAGENT_MODEL="deepseek/deepseek-chat"
    export DEEPSEEK_API_KEY="your-api-key"
    ```

=== "OpenAI-compatible Gateway"

    ```bash
    export OPENAGENT_MODEL="openai/my-model"
    export OPENAGENT_API_KEY="gateway-key"
    export OPENAGENT_BASE_URL="https://gateway.example.com/v1"
    ```

## 5. 启动并验证

```bash
uvicorn app:app --reload
```

打开以下地址：

- `http://127.0.0.1:8000/_agent/`：Agent 独立页；
- `http://127.0.0.1:8000/_agent/widget/`：Widget；
- `http://127.0.0.1:8000/docs`：FastAPI Swagger UI；
- `http://127.0.0.1:8000/_agent/openapi`：Agent 实际看到的 OpenAPI 快照。

先尝试：

> network 团队有哪些库存？

Agent 会先选择 `list_inventory_items`，加载它的完整契约，再调用宿主应用内的 `GET /items?owner=network`。

!!! warning "写操作默认关闭"

    `POST`、`PUT`、`PATCH`、`DELETE` 等操作不会默认执行。请阅读[认证与安全](guides/security.md)后再开启。

下一步：按[OpenAPI 质量指南](guides/openapi-quality.md)检查真实接口，再完成[模型与运行参数](guides/configuration.md)配置。
