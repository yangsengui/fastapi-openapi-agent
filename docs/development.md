# 开发与贡献

## 本地环境

```bash
pip install -e ".[dev,llm,docs]"
npm install --prefix frontend
npm run build --prefix frontend
```

运行 Demo：

```bash
python -m uvicorn examples.demo:app --reload
```

打开 `http://127.0.0.1:8000/_agent/`。

## 文档

本地预览：

```bash
mkdocs serve
```

严格构建：

```bash
mkdocs build --strict
```

文档源码位于 `docs/`，导航位于 `mkdocs.yml`。中文是根路径下的默认语言，英文翻译使用 `.en.md` 后缀并发布到 `/en/`。新增面向用户的页面必须同时提供两个语言版本；`fallback_to_default: false` 会让 CI 拒绝缺少翻译的页面。内部链接始终使用不带语言后缀的相对路径。

仓库的 `Documentation` workflow 会在 pull request 中严格构建，并在 `main` 的文档变更后部署 GitHub Pages。部署成功后，README 顶部的 `docs online` 徽章和仓库的 `github-pages` deployment 都会指向在线文档。

首次启用时，需要在 GitHub 仓库 **Settings → Pages → Build and deployment → Source** 中选择 **GitHub Actions**。也建议在仓库 **About → Website** 中填写 `https://yangsengui.github.io/fastapi-openapi-agent/`，让链接同时显示在仓库右侧简介区域。

## 验证

```bash
npm run check --prefix frontend
npm run build --prefix frontend
pytest
mkdocs build --strict
```

## 前端产物

`npm run build --prefix frontend` 会生成：

- `src/openagent/static/sidebar.js`
- `src/openagent/static/widget/`

这些静态文件会被打进 Python wheel，PyPI 用户无需安装 Node.js。

## 提交建议

- 行为变化补测试；
- 用户可见变化补文档和 `CHANGELOG.md`；
- 不提交 `.env`、模型密钥或真实用户数据；
- 对 OpenAPI 行为变化同时覆盖目录、契约读取和执行保护。
- 保持中文与英文文档页面同步。

项目使用 MIT License。提交代码即表示贡献内容可按该许可证分发。
