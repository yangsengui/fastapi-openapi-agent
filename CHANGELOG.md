# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning after the first public release.

## Unreleased

- Added a Django Ninja adapter with UI, JSON and SSE chat routes, schema discovery, forwarded authentication headers, and in-process ASGI host API execution.
- Added integration-time `en` and `zh` language selection for the widget, built-in responder, runtime messages, and LiteLLM output instructions.
- Added a MkDocs Material documentation site covering the OpenAPI-to-Agent workflow, OpenAPI quality, configuration, embedding, security, API reference, and GitHub Pages deployment.

## 0.1.0 - 2026-07-20

- Initial FastAPI adapter for mounting an OpenAPI-aware agent under `/_agent`.
- Embeddable iframe widget and `sidebar.js` loader.
- Deterministic local OpenAPI responder for offline development.
- Provider-neutral LiteLLM responder with OpenAPI tool-calling support; DeepSeek is now just a LiteLLM model prefix.
- In-process ASGI operation execution for host FastAPI APIs.
- Parent-page request bridge for custom authentication and request handling.
- Core customization SDK with an operation catalog, typed contracts and stream events, and pluggable Agent backends.
