# 前端嵌入

## 浮动侧边栏

宿主页面与 API 同源时只需：

```html
<script src="/_agent/sidebar.js"></script>
```

完整配置：

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    title: "API Assistant",
    welcomeTitle: "有什么可以帮你？",
    description: "查询业务数据或了解 API 能力。",
    language: "zh",
    open: false,
    width: 560,
    minWidth: 420,
    maxWidth: 920
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

侧边栏支持拖拽调整宽度，并持久化用户选择。快捷键为 `Ctrl/Cmd + E`。

## 嵌入指定容器

```html
<div id="agent-root"></div>
<script>
  window.OpenAgent = {
    baseUrl: "/_agent",
    container: "#agent-root",
    language: "zh"
  };
</script>
<script src="/_agent/sidebar.js"></script>
```

## 接入现有认证请求层

Widget 在 iframe 中运行。可通过 `window.OpenAgent.request` 把请求交给父页面，从而复用 token 刷新、租户头、签名或 cookie 策略：

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    async request(input) {
      const token = await getAccessToken();

      return fetch(input.url, {
        method: input.method,
        headers: {
          ...input.headers,
          Authorization: `Bearer ${token}`,
          "X-Tenant-ID": getTenantId()
        },
        body: input.body,
        credentials: "include"
      });
    }
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

`request(input)` 必须返回标准 `fetch` Response。流式响应会按 chunk 转发给 iframe。桥接层只允许访问配置的 `baseUrl` 下的路径。

## 跨域注意事项

- 只允许可信前端 origin 访问 Agent 路由；
- 不要使用通配 CORS 同时开启凭证；
- 在父页面附加短期 token，并保持最小 scope；
- 服务端仍需验证身份和权限，不能把 iframe 隔离当作安全边界。
