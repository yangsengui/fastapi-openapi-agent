from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional, Protocol
from urllib.parse import quote

from .catalog import OperationCatalog, OperationContract


class OperationInvoker(Protocol):
    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Dict[str, Any],
        headers: Dict[str, str],
        body: Any,
    ) -> Any:
        """Execute one API operation and return an HTTP-response-like object."""


class OpenAPIAgentRuntime:
    """Framework-neutral runtime for OpenAPI operation tools.

    Framework adapters provide an ``OperationInvoker`` when live API execution is
    enabled. Without an invoker, the runtime can still search and inspect the
    OpenAPI document.
    """

    def __init__(
        self,
        openapi: Dict[str, Any],
        *,
        invoker: Optional[OperationInvoker] = None,
        agent_path: str = "/_agent",
        enable_api_calls: bool = True,
        allow_mutating_api_calls: bool = False,
        forwarded_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.openapi = openapi
        self.invoker = invoker
        self.agent_path = agent_path.rstrip("/") or "/_agent"
        self.enable_api_calls = enable_api_calls
        self.allow_mutating_api_calls = allow_mutating_api_calls
        self.forwarded_headers = dict(forwarded_headers or {})
        self.catalog = OperationCatalog.from_openapi(openapi)
        self._loaded_operations: set[tuple[str, str]] = set()

    async def run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "operation_search":
            return self.operation_search(args)
        if name == "operation_get":
            return self.operation_get(args)
        if name == "operation_request":
            return await self.operation_request(args)
        return _failure(name, args, f"Unknown tool: {name}")

    def operation_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = _search_text(args)
        method = _string(args.get("method")).upper()
        operation_id = _string(args.get("operationId") or args.get("operation"))
        limit = _int(args.get("limit"), 8)
        hits = self.catalog.search_operations(
            query,
            method=method or None,
            operation_id=operation_id or None,
            limit=max(1, min(limit, 20)),
        )
        return {
            "ok": True,
            "tool_name": "operation_search",
            "input": args,
            "data": {"operations": [_dump_model(hit) for hit in hits]},
            "preview": f"Found {len(hits)} operation(s).",
        }

    def operation_get(self, args: Dict[str, Any]) -> Dict[str, Any]:
        record = self._find_operation(args)
        if not record:
            return _failure("operation_get", args, "Operation not found.")
        method = record.metadata.method
        path = record.metadata.path
        self._loaded_operations.add((method, path))
        data = {
            "operation": _dump_model(record.metadata),
            "risk": record.risk,
            "openapi_operation": record.openapi_operation,
            "component_schemas": record.component_schemas,
        }
        return {
            "ok": True,
            "tool_name": "operation_get",
            "method": method,
            "path": path,
            "input": args,
            "data": data,
            "preview": f"Loaded contract for {method} {path}.",
        }

    async def operation_request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enable_api_calls:
            return _failure("operation_request", args, "API calls are disabled for this agent.")
        if self.invoker is None:
            return _failure("operation_request", args, "API calls require an operation invoker.")

        record = self._find_operation(args)
        if not record:
            return _failure("operation_request", args, "Operation not found.")
        method = record.metadata.method
        path_template = record.metadata.path
        if (method, path_template) not in self._loaded_operations:
            return _failure(
                "operation_request",
                args,
                "Operation contract must be loaded with operation_get before execution.",
                method=method,
                path=path_template,
            )
        if path_template.startswith(self.agent_path + "/") or path_template == self.agent_path:
            return _failure("operation_request", args, "Agent internal routes cannot be called.")

        risk = record.risk
        if risk != "read_only" and not self.allow_mutating_api_calls:
            return {
                "ok": False,
                "tool_name": "operation_request",
                "method": method,
                "path": path_template,
                "input": args,
                "data": {"requires_approval": True, "risk": risk},
                "preview": f"Blocked {method} {path_template}: mutating API calls are disabled.",
                "error": "Mutating API calls require allow_mutating_api_calls=True.",
            }

        path_params = _dict(args.get("pathParams") or args.get("path_params"))
        query = _dict(args.get("query"))
        headers = self._request_headers(_dict(args.get("headers")))
        body = args.get("body")

        try:
            path = _render_path(path_template, path_params)
        except ValueError as exc:
            return _failure("operation_request", args, str(exc), method=method, path=path_template)

        try:
            response = await self.invoker.request(
                method,
                path,
                query=query,
                headers=headers,
                body=body,
            )
        except Exception as exc:  # Adapter implementations normalize framework errors here.
            return _failure(
                "operation_request",
                args,
                f"Internal API request failed: {exc.__class__.__name__}.",
                method=method,
                path=path_template,
            )

        content_type = _header_value(getattr(response, "headers", {}), "content-type")
        data = _response_data(response, content_type)
        status_code = int(getattr(response, "status_code", 0))
        ok = status_code < 400
        return {
            "ok": ok,
            "tool_name": "operation_request",
            "method": method,
            "path": path_template,
            "status": status_code,
            "content_type": content_type,
            "input": args,
            "data": data,
            "preview": f"{method} {path_template} -> {status_code}",
            **({} if ok else {"error": f"HTTP {status_code}"}),
        }

    def _find_operation(self, args: Dict[str, Any]) -> Optional[OperationContract]:
        operation_id = _string(args.get("operation") or args.get("operationId") or args.get("operation_id"))
        method_arg = _string(args.get("method"))
        path_arg = _string(args.get("path"))
        return self.catalog.find_operation(
            operation_id=operation_id or None,
            method=method_arg or None,
            path=path_arg or None,
        )

    def _request_headers(self, explicit: Dict[str, Any]) -> Dict[str, str]:
        headers = {str(name): str(value) for name, value in self.forwarded_headers.items()}
        for name, value in explicit.items():
            if value is not None:
                headers[str(name)] = str(value)
        return headers


def _dump_model(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _search_text(args: Dict[str, Any]) -> str:
    parts = [
        _string(args.get("query")),
        _string(args.get("text")),
        _string(args.get("businessAction")),
        _string(args.get("businessResource")),
    ]
    queries = args.get("queries")
    if isinstance(queries, list):
        for item in queries:
            if isinstance(item, dict):
                parts.extend(_string(item.get(key)) for key in ("query", "businessAction", "businessResource", "method"))
            else:
                parts.append(_string(item))
    return " ".join(part for part in parts if part)


def _render_path(path_template: str, params: Dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params or params[key] is None:
            raise ValueError(f"Missing required path parameter: {key}")
        return quote(str(params[key]), safe="")

    return re.sub(r"\{([^{}]+)\}", replace, path_template)


def _response_data(response: Any, content_type: str) -> Any:
    if "application/json" in content_type.lower():
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            pass
    text = str(getattr(response, "text", ""))
    if len(text) > 50000:
        return {"text": text[:50000], "truncated": True}
    return text


def _header_value(headers: Any, name: str) -> str:
    if hasattr(headers, "get"):
        return str(headers.get(name) or "")
    return ""


def _failure(
    tool_name: str,
    args: Dict[str, Any],
    error: str,
    *,
    method: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "tool_name": tool_name,
        "method": method,
        "path": path,
        "input": args,
        "error": error,
        "preview": error,
    }


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
