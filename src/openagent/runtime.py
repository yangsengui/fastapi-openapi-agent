from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional, Protocol
from urllib.parse import quote

from .responder import OperationHit, _iter_operations, _rank_operations


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


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

    async def run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "operation_search":
            return self.operation_search(args)
        if name == "operation_get":
            return self.operation_get(args)
        if name == "operation_request":
            return await self.operation_request(args)
        return _failure(name, args, f"Unknown tool: {name}")

    def operation_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        operations = list(_iter_operations(self.openapi))
        query = _search_text(args)
        method = _string(args.get("method")).upper()
        operation_id = _string(args.get("operationId") or args.get("operation"))

        if operation_id:
            hits = [op for op in operations if op.operation_id == operation_id]
        else:
            hits = _rank_operations(query, operations) if query else operations[:8]
        if method:
            hits = [op for op in hits if op.method == method]

        limit = _int(args.get("limit"), 8)
        hits = hits[: max(1, min(limit, 20))]
        return {
            "ok": True,
            "tool_name": "operation_search",
            "input": args,
            "data": {"operations": [_dump_operation(hit) for hit in hits]},
            "preview": f"Found {len(hits)} operation(s).",
        }

    def operation_get(self, args: Dict[str, Any]) -> Dict[str, Any]:
        record = self._find_operation(args)
        if not record:
            return _failure("operation_get", args, "Operation not found.")
        method, path, operation = record
        hit = _operation_hit(method, path, operation)
        data = {
            "operation": _dump_operation(hit),
            "risk": _operation_risk(method, operation),
            "openapi_operation": operation,
            "component_schemas": _component_schemas_for_value(self.openapi, operation),
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
        method, path_template, operation = record
        if path_template.startswith(self.agent_path + "/") or path_template == self.agent_path:
            return _failure("operation_request", args, "Agent internal routes cannot be called.")

        risk = _operation_risk(method, operation)
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

    def _find_operation(self, args: Dict[str, Any]) -> Optional[tuple[str, str, Dict[str, Any]]]:
        operation_id = _string(args.get("operation") or args.get("operationId") or args.get("operation_id"))
        method_arg = _string(args.get("method")).lower()
        path_arg = _string(args.get("path"))
        paths = self.openapi.get("paths") or {}
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if operation_id and operation.get("operationId") == operation_id:
                    return method.upper(), path, operation
                if path_arg and method_arg and path == path_arg and method.lower() == method_arg:
                    return method.upper(), path, operation
        return None

    def _request_headers(self, explicit: Dict[str, Any]) -> Dict[str, str]:
        headers = {str(name): str(value) for name, value in self.forwarded_headers.items()}
        for name, value in explicit.items():
            if value is not None:
                headers[str(name)] = str(value)
        return headers


def _operation_hit(method: str, path: str, operation: Dict[str, Any]) -> OperationHit:
    return OperationHit(
        method=method.upper(),
        path=path,
        operation_id=operation.get("operationId"),
        summary=operation.get("summary"),
        description=operation.get("description"),
        tags=list(operation.get("tags") or []),
        parameters=[_parameter_name(parameter) for parameter in operation.get("parameters") or []],
        request_body="requestBody" in operation,
        responses=list((operation.get("responses") or {}).keys()),
    )


def _operation_risk(method: str, operation: Dict[str, Any]) -> str:
    metadata = operation.get("x-acp-operation") or {}
    risk = metadata.get("risk") if isinstance(metadata, dict) else None
    if isinstance(risk, str) and risk.strip():
        return risk.strip()
    return "read_only" if method.upper() in READ_ONLY_METHODS else "mutating"


def _parameter_name(parameter: Dict[str, Any]) -> str:
    name = parameter.get("name")
    location = parameter.get("in")
    if name and location:
        return f"{name} ({location})"
    return str(name or "")


def _dump_operation(operation: OperationHit) -> Dict[str, Any]:
    if hasattr(operation, "model_dump"):
        return operation.model_dump()
    return operation.dict()


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


def _component_schemas_for_value(openapi: Dict[str, Any], value: Any) -> Dict[str, Any]:
    schemas = ((openapi.get("components") or {}).get("schemas") or {})
    names: set[str] = set()
    _collect_refs(value, names)
    previous_size = -1
    while previous_size != len(names):
        previous_size = len(names)
        for name in list(names):
            schema = schemas.get(name)
            if schema:
                _collect_refs(schema, names)
    return {name: schemas[name] for name in sorted(names) if name in schemas}


def _collect_refs(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            names.add(ref.rsplit("/", 1)[-1])
        for child in value.values():
            _collect_refs(child, names)
    elif isinstance(value, list):
        for child in value:
            _collect_refs(child, names)


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
