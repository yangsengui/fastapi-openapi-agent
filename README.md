# openagent

一个 OpenAPI-native API Agent 框架：核心逻辑基于 OpenAPI schema 工作，FastAPI 只是当前第一个 adapter。

## 功能

- `openagent` 提供框架无关的 OpenAPI operation 检索、contract 获取和 tool runtime。
- `openagent.fastapi.install_openapi_agent(app)` 一行接入现有 FastAPI 应用。
- FastAPI adapter 自动读取当前应用 OpenAPI schema。
- 提供 agent 页面：默认路径 `/_agent/`。
- 提供静态嵌入脚本：`/_agent/sidebar.js`，脚本只负责挂载 iframe。
- Agent UI 是独立 React/Vite SPA，构建后由 FastAPI 从 `/_agent/widget/` 提供。
- 默认内置本地检索式 responder，方便离线开发和验证。
- 可传入自定义 responder 接入真实 LLM 或内部 agent 平台。
- DeepSeek 模式支持 agent tool-calling：`operation_search`、`operation_get`、`operation_request`。
- `operation_request` 通过 ASGI 在进程内调用宿主 FastAPI，不额外走公网 HTTP。
- 提供 `/chat/stream` SSE 接口，按事件流输出文本增量和工具调用链。

## 快速开始

```bash
devyard run install
devyard run build
devyard up -d
devyard status
```

打开 devyard 输出的 `api` 地址：

- `/_agent/`：独立 agent 页面。
- `/_agent/widget/`：React SPA widget。
- `/docs`：FastAPI Swagger 文档。
- `/_agent/sidebar.js`：可嵌入侧边栏组件。

## 包结构

```text
openagent                  # 框架无关核心：models、responder、runtime、DeepSeek tool-calling
openagent.fastapi          # FastAPI adapter：路由挂载、静态资源、ASGI 进程内调用
```

## FastAPI 接入

```python
from fastapi import FastAPI
from openagent.fastapi import install_openapi_agent

app = FastAPI(title="My API")

install_openapi_agent(app)
```

启用 API 调用 agent 能力：

```python
install_openapi_agent(
    app,
    enable_api_calls=True,
    allow_mutating_api_calls=False,  # 默认只允许 GET/HEAD/OPTIONS
)
```

如果你的业务明确允许 agent 执行写操作，可以显式开启：

```python
install_openapi_agent(app, allow_mutating_api_calls=True)
```

自定义路径和标题：

```python
install_openapi_agent(
    app,
    path="/api-agent",
    title="Service Agent",
    description="Ask questions about this service API.",
)
```

## 前端嵌入

在任意页面加入脚本即可新增悬浮侧边栏：

```html
<script src="/_agent/sidebar.js"></script>
```

`sidebar.js` 由 `frontend/src/sidebar-loader.ts` 构建生成，只负责：

- 创建右下角启动按钮。
- 创建 iframe 并加载 `/_agent/widget/`。
- 支持嵌入到指定容器。
- 侧边栏默认 `560px` 宽、撑满视口高度，左侧拖拽可调整宽度并记住设置。
- 支持 `Ctrl/Cmd + E` 切换浮窗。

主体聊天 UI、流式输出、工具调用链、历史会话和 Markdown 渲染都在 `frontend/src/App.tsx` SPA 中实现。

侧边栏默认优先调用 `/_agent/chat/stream`：

- `text-delta`：模型回答增量。
- `tool-input-start` / `tool-input-available`：工具调用开始和入参。
- `tool-output-available` / `tool-output-error`：工具输出或失败。
- `finish`：最终回答、命中的 OpenAPI operations 和完整 tool results。

如果流式接口不可用，前端会自动回退到 `/_agent/chat`。

如果前端和 FastAPI 不在同一路径，可以显式配置：

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    title: "API Assistant",
    open: false,
    width: 560,
    minWidth: 420,
    maxWidth: 920
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

也可以嵌入到指定容器，而不是悬浮侧边栏：

```html
<div id="agent-root"></div>
<script>
  window.OpenAgent = { baseUrl: "/_agent", container: "#agent-root" };
</script>
<script src="/_agent/sidebar.js"></script>
```

## 接入真实 LLM

默认 responder 不调用外部模型，只基于 OpenAPI 文本做确定性匹配。

### DeepSeek

设置环境变量后，示例应用会自动使用 DeepSeek：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
devyard up -d
```

在自己的 FastAPI 应用中显式接入：

```python
from openagent.deepseek import create_deepseek_responder
from openagent.fastapi import install_openapi_agent

install_openapi_agent(app, responder=create_deepseek_responder())
```

如果没有显式传入 `responder`，并且环境变量里存在 `DEEPSEEK_API_KEY`，插件会自动启用带工具调用能力的 DeepSeek agent。

API 执行的标准调用链是：

```text
operation_search -> operation_get -> operation_request -> final answer
```

流式模式会先强制执行一次 `operation_search` 预检，保证前端能展示完整调用链；随后模型基于搜索结果继续读取 contract 并执行 API。

可以调整模型：

```python
install_openapi_agent(
    app,
    responder=create_deepseek_responder(model="deepseek-chat"),
)
```

### 自定义 responder

生产环境也可以传入任意自定义 responder：

```python
from openagent import AgentRequest, AgentResponse
from openagent.fastapi import install_openapi_agent

async def my_responder(request: AgentRequest, openapi: dict) -> AgentResponse:
    # 在这里调用你的 LLM，把 openapi 作为上下文或工具信息传入。
    return AgentResponse(answer="LLM response", operations=[], sources=[])

install_openapi_agent(app, responder=my_responder)
```

## 本地命令

```bash
devyard run install
devyard run build
devyard run test
devyard up -d
devyard logs -f api
devyard down
```

前端单独开发：

```bash
npm run dev --prefix frontend
npm run check --prefix frontend
npm run build --prefix frontend
```
