from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Literal, Optional, Set

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: List[AgentMessage] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class OperationHit(BaseModel):
    method: str
    path: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list)
    request_body: bool = False
    responses: List[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    answer: str
    operations: List[OperationHit] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    tool_results: List["AgentToolResult"] = Field(default_factory=list)


class AgentToolResult(BaseModel):
    tool_name: str
    ok: bool = True
    method: Optional[str] = None
    path: Optional[str] = None
    status: Optional[int] = None
    content_type: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    data: Any = None
    preview: Optional[str] = None
    error: Optional[str] = None


HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
STOP_WORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "api",
    "are",
    "can",
    "for",
    "how",
    "i",
    "in",
    "is",
    "list",
    "me",
    "of",
    "on",
    "or",
    "show",
    "the",
    "to",
    "what",
    "which",
    "with",
    "接口",
    "哪些",
    "所有",
    "一下",
    "可以",
    "怎么",
    "如何",
}


def default_openapi_responder(request: AgentRequest, openapi: Dict[str, Any]) -> AgentResponse:
    """Small deterministic OpenAPI responder used when no LLM backend is wired.

    It ranks operations by token overlap, then formats a concise answer. This is
    enough for local/offline demos and gives custom LLM responders a stable data
    contract to replace later.
    """

    operations = list(_iter_operations(openapi))
    if not operations:
        return AgentResponse(answer="I could not find any operations in the OpenAPI schema.")

    message = request.message.strip()
    hits = _rank_operations(message, operations)
    if not hits:
        hits = operations[:8]

    answer = _format_answer(openapi, message, hits)
    return AgentResponse(
        answer=answer,
        operations=hits,
        sources=[f"{hit.method} {hit.path}" for hit in hits],
    )


def _iter_operations(openapi: Dict[str, Any]) -> Iterable[OperationHit]:
    paths = openapi.get("paths", {}) or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            yield OperationHit(
                method=method.upper(),
                path=path,
                operation_id=operation.get("operationId"),
                summary=operation.get("summary"),
                description=operation.get("description"),
                tags=list(operation.get("tags") or []),
                parameters=_parameter_names(operation.get("parameters") or []),
                request_body="requestBody" in operation,
                responses=list((operation.get("responses") or {}).keys()),
            )


def _parameter_names(parameters: Iterable[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for parameter in parameters:
        name = parameter.get("name")
        location = parameter.get("in")
        if name and location:
            names.append(f"{name} ({location})")
        elif name:
            names.append(name)
    return names


def _rank_operations(message: str, operations: List[OperationHit]) -> List[OperationHit]:
    query_tokens = _tokens(message)
    method_tokens = {token.upper() for token in query_tokens if token in HTTP_METHODS}
    if not query_tokens and not method_tokens:
        return operations[:8]

    scored = []
    for operation in operations:
        haystack = " ".join(
            filter(
                None,
                [
                    operation.method,
                    operation.path,
                    operation.operation_id or "",
                    operation.summary or "",
                    operation.description or "",
                    " ".join(operation.tags),
                    " ".join(operation.parameters),
                ],
            )
        )
        operation_tokens = _tokens(haystack)
        overlap = len(query_tokens & operation_tokens)
        method_bonus = 2 if not method_tokens or operation.method in method_tokens else 0
        path_bonus = 1 if any(token in operation.path.lower() for token in query_tokens) else 0
        score = overlap + method_bonus + path_bonus
        if score > 0:
            scored.append((score, operation))

    scored.sort(key=lambda item: (-item[0], item[1].path, item[1].method))
    return [operation for _, operation in scored[:8]]


def _tokens(value: str) -> Set[str]:
    raw = re.findall(r"[\w\u4e00-\u9fff]+", value.lower())
    return {token for token in raw if len(token) > 1 and token not in STOP_WORDS}


def _format_answer(openapi: Dict[str, Any], message: str, hits: List[OperationHit]) -> str:
    title = (openapi.get("info") or {}).get("title") or "this API"
    lines = [f"Based on {title}'s OpenAPI schema, these endpoints look most relevant to: {message}"]
    for hit in hits:
        label = hit.summary or hit.operation_id or "No summary"
        details = []
        if hit.parameters:
            details.append("params: " + ", ".join(hit.parameters))
        if hit.request_body:
            details.append("request body")
        if hit.responses:
            details.append("responses: " + ", ".join(hit.responses[:5]))
        suffix = f" ({'; '.join(details)})" if details else ""
        lines.append(f"- {hit.method} {hit.path}: {label}{suffix}")
    lines.append("For production use, pass a custom responder that calls your LLM and uses the same OpenAPI schema as tool context.")
    return "\n".join(lines)
