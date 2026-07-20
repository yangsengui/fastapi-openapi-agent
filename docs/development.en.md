# Development and contribution

## Local environment

```bash
pip install -e ".[dev,llm,docs]"
npm install --prefix frontend
npm run build --prefix frontend
```

Run the demo:

```bash
python -m uvicorn examples.demo:app --reload
```

Open `http://127.0.0.1:8000/_agent/`.

## Documentation

Preview locally:

```bash
mkdocs serve
```

Build in strict mode:

```bash
mkdocs build --strict
```

Documentation source lives under `docs/` and navigation is defined in `mkdocs.yml`. English is the default language at the site root and uses the `.en.md` suffix. Chinese translations use `.zh.md` and are published under `/zh/`. Every new user-facing page should ship in both languages; `fallback_to_default: false` makes CI reject missing translations.

The `Documentation` workflow builds every pull request and deploys GitHub Pages after changes reach `main`. A successful deployment updates the `github-pages` environment and the `docs online` badge in the repository README points to the live site.

## Validation

```bash
npm run check --prefix frontend
npm run build --prefix frontend
pytest
mkdocs build --strict
```

## Frontend artifacts

`npm run build --prefix frontend` generates:

- `src/openagent/static/sidebar.js`
- `src/openagent/static/widget/`

These assets are included in the Python wheel, so PyPI users do not need Node.js.

## Contribution guidelines

- Add tests for behavior changes.
- Document user-visible changes and update `CHANGELOG.md`.
- Never commit `.env`, model credentials, or real user data.
- Cover catalog discovery, contract loading, and execution policy when changing OpenAPI behavior.
- Keep Chinese and English documentation pages synchronized.

The project uses the MIT License. By submitting code, you agree that your contribution may be distributed under that license.
