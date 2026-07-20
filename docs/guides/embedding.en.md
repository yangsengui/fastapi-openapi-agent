# Frontend embedding

## Floating sidebar

For a page served from the same origin as the API:

```html
<script src="/_agent/sidebar.js"></script>
```

Full configuration:

```html
<script>
  window.OpenAgent = {
    baseUrl: "https://api.example.com/_agent",
    title: "API Assistant",
    welcomeTitle: "How can I help?",
    description: "Query business data or explore API capabilities.",
    language: "en",
    open: false,
    width: 560,
    minWidth: 420,
    maxWidth: 920
  };
</script>
<script src="https://api.example.com/_agent/sidebar.js"></script>
```

The sidebar is resizable and persists the selected width. Use `Ctrl/Cmd + E` to toggle it.

## Embed in a container

```html
<div id="agent-root"></div>
<script>
  window.OpenAgent = {
    baseUrl: "/_agent",
    container: "#agent-root",
    language: "en"
  };
</script>
<script src="/_agent/sidebar.js"></script>
```

## Reuse an existing authenticated request layer

The widget runs inside an iframe. `window.OpenAgent.request` delegates requests to the parent page so it can reuse token refresh, tenant headers, request signing, or cookie policy:

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

`request(input)` must return a standard `fetch` Response. Streaming bodies are forwarded to the iframe chunk by chunk. The bridge only accepts URLs under the configured `baseUrl`.

## Cross-origin considerations

- Allow only trusted frontend origins to access Agent routes.
- Do not combine wildcard CORS with credentials.
- Attach short-lived tokens in the parent page with the smallest required scopes.
- Always enforce authentication and authorization on the server; iframe isolation is not a security boundary.
