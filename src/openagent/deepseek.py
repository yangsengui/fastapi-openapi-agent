from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Iterable, Optional, Set

import httpx

from .responder import AgentRequest, AgentResponse, AgentToolResult, default_openapi_responder

Responder = Callable[[AgentRequest, Dict[str, Any]], Awaitable[AgentResponse]]
ToolRunner = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


async def stream_deepseek_agent(
    request: AgentRequest,
    openapi: Dict[str, Any],
    tool_runner: ToolRunner,
    api_key: Optional[str] = None,
    *,
    model: str = "deepseek-chat",
    base_url: str = "https://api.deepseek.com",
    temperature: float = 0.2,
    timeout: float = 30.0,
    max_context_chars: int = 16000,
    trust_env: bool = False,
    max_tool_rounds: int = 6,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream a DeepSeek tool-calling agent run as UI-friendly event chunks."""

    resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not resolved_api_key:
        yield {"type": "error", "errorText": "DEEPSEEK_API_KEY is not set."}
        return

    grounding = default_openapi_responder(request, openapi)
    messages: list[dict[str, Any]] = _build_messages(request, openapi, grounding, max_context_chars)
    tool_results: list[Dict[str, Any]] = []
    final_text_parts: list[str] = []
    text_id = "text-1"

    yield {"type": "start", "messageId": _stream_id("assistant")}

    initial_search_args = {"query": request.message, "limit": 8}
    initial_search_id = _stream_id("operation_search")
    yield {
        "type": "tool-input-start",
        "toolCallId": initial_search_id,
        "toolName": "operation_search",
    }
    yield {
        "type": "tool-input-available",
        "toolCallId": initial_search_id,
        "toolName": "operation_search",
        "input": initial_search_args,
    }
    initial_search_result = await tool_runner("operation_search", initial_search_args)
    tool_results.append(initial_search_result)
    if initial_search_result.get("ok") is False:
        yield {
            "type": "tool-output-error",
            "toolCallId": initial_search_id,
            "toolName": "operation_search",
            "output": initial_search_result,
            "errorText": str(initial_search_result.get("error") or "operation_search failed"),
        }
    else:
        yield {
            "type": "tool-output-available",
            "toolCallId": initial_search_id,
            "toolName": "operation_search",
            "output": initial_search_result,
        }
    messages.append(
        {
            "role": "system",
            "content": (
                "A preliminary operation_search has already been executed for the latest user request. "
                "Use that result as the first step in the call chain, then call operation_get for the selected operation, "
                "then call operation_request if live data or action execution is needed. operation_search result:\n"
                + json.dumps(initial_search_result, ensure_ascii=False, default=str)
            ),
        }
    )

    async with httpx.AsyncClient(timeout=timeout, transport=transport, trust_env=trust_env) as client:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "tools": _tool_definitions(),
            "tool_choice": "auto",
            "stream": True,
        }

        for round_index in range(max(1, max_tool_rounds)):
            tool_call_state: dict[int, dict[str, Any]] = {}
            text_started = False
            try:
                async with client.stream(
                    "POST",
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {resolved_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for chunk in _iter_openai_stream_chunks(response):
                        choice = (chunk.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        content = delta.get("content")
                        if content:
                            if not text_started:
                                text_started = True
                                yield {"type": "text-start", "id": text_id}
                            final_text_parts.append(content)
                            yield {"type": "text-delta", "id": text_id, "delta": content}

                        for call_delta in delta.get("tool_calls") or []:
                            index = int(call_delta.get("index") or 0)
                            state = tool_call_state.setdefault(
                                index,
                                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                            )
                            if call_delta.get("id"):
                                state["id"] = call_delta["id"]
                            if call_delta.get("type"):
                                state["type"] = call_delta["type"]
                            fn_delta = call_delta.get("function") or {}
                            fn_state = state.setdefault("function", {"name": "", "arguments": ""})
                            if fn_delta.get("name"):
                                fn_state["name"] = fn_delta["name"]
                                yield {
                                    "type": "tool-input-start",
                                    "toolCallId": state.get("id") or f"tool-{round_index}-{index}",
                                    "toolName": fn_state["name"],
                                }
                            if fn_delta.get("arguments"):
                                fn_state["arguments"] = str(fn_state.get("arguments") or "") + fn_delta["arguments"]
            except httpx.HTTPStatusError as exc:
                yield {"type": "error", "errorText": f"DeepSeek request failed with HTTP {exc.response.status_code}."}
                return
            except httpx.HTTPError as exc:
                yield {"type": "error", "errorText": f"DeepSeek request failed: {exc.__class__.__name__}."}
                return

            tool_calls = [tool_call_state[index] for index in sorted(tool_call_state)]
            if not tool_calls:
                if text_started:
                    yield {"type": "text-end", "id": text_id}
                yield {
                    "type": "finish",
                    "response": _agent_response_payload(grounding, "".join(final_text_parts), tool_results),
                }
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(final_text_parts) if round_index == 0 else "",
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                name, args = _tool_call_args(tool_call)
                tool_call_id = str(tool_call.get("id") or name or _stream_id("tool"))
                yield {
                    "type": "tool-input-available",
                    "toolCallId": tool_call_id,
                    "toolName": name,
                    "input": args,
                }
                result = await tool_runner(name, args)
                tool_results.append(result)
                if result.get("ok") is False:
                    yield {
                        "type": "tool-output-error",
                        "toolCallId": tool_call_id,
                        "toolName": name,
                        "output": result,
                        "errorText": str(result.get("error") or result.get("preview") or "Tool execution failed"),
                    }
                else:
                    yield {
                        "type": "tool-output-available",
                        "toolCallId": tool_call_id,
                        "toolName": name,
                        "output": result,
                    }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

            payload["messages"] = messages

    yield {
        "type": "error",
        "errorText": "The agent reached the maximum tool-calling rounds before producing a final answer.",
    }


def create_deepseek_responder(
    api_key: Optional[str] = None,
    *,
    model: str = "deepseek-chat",
    base_url: str = "https://api.deepseek.com",
    temperature: float = 0.2,
    timeout: float = 30.0,
    max_context_chars: int = 16000,
    trust_env: bool = False,
    tool_runner: Optional[ToolRunner] = None,
    max_tool_rounds: int = 4,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Responder:
    """Create a DeepSeek-backed responder for OpenAgent adapters."""

    resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set.")

    async def responder(request: AgentRequest, openapi: Dict[str, Any]) -> AgentResponse:
        grounding = default_openapi_responder(request, openapi)
        messages = _build_messages(request, openapi, grounding, max_context_chars)
        tool_results: list[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=transport,
                trust_env=trust_env,
            ) as client:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tool_runner is not None:
                    payload["tools"] = _tool_definitions()
                    payload["tool_choice"] = "auto"

                for _ in range(max(1, max_tool_rounds)):
                    response = await client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {resolved_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()
                    message = _extract_message(response.json())
                    tool_calls = message.get("tool_calls") or []
                    if tool_runner is None or not tool_calls:
                        answer = _message_content(message)
                        return AgentResponse(
                            answer=answer,
                            operations=grounding.operations,
                            sources=grounding.sources,
                            tool_results=[_tool_result_model(item) for item in tool_results],
                        )

                    messages.append(_assistant_tool_message(message))
                    for tool_call in tool_calls:
                        name, args = _tool_call_args(tool_call)
                        result = await tool_runner(name, args)
                        tool_results.append(result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": str(tool_call.get("id") or name),
                                "name": name,
                                "content": json.dumps(result, ensure_ascii=False, default=str),
                            }
                        )
                    payload["messages"] = messages

                return AgentResponse(
                    answer="The agent reached the maximum tool-calling rounds before producing a final answer.",
                    operations=grounding.operations,
                    sources=grounding.sources,
                    tool_results=[_tool_result_model(item) for item in tool_results],
                )
        except httpx.HTTPStatusError as exc:
            return _fallback_response(
                grounding,
                f"DeepSeek request failed with HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return _fallback_response(
                grounding,
                f"DeepSeek request failed: {exc.__class__.__name__}.",
            )

    return responder


async def _iter_openai_stream_chunks(response: httpx.Response) -> AsyncIterator[Dict[str, Any]]:
    async for line in response.aiter_lines():
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def _agent_response_payload(
    grounding: AgentResponse, answer: str, tool_results: list[Dict[str, Any]]
) -> Dict[str, Any]:
    response = AgentResponse(
        answer=answer or "DeepSeek returned an empty answer.",
        operations=grounding.operations,
        sources=grounding.sources,
        tool_results=[_tool_result_model(item) for item in tool_results],
    )
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


def _stream_id(prefix: str) -> str:
    import secrets

    return f"{prefix}_{secrets.token_hex(6)}"


def _build_messages(
    request: AgentRequest,
    openapi: Dict[str, Any],
    grounding: AgentResponse,
    max_context_chars: int,
) -> list[dict[str, str]]:
    context = {
        "api": openapi.get("info") or {},
        "servers": openapi.get("servers") or [],
        "relevant_operations": _operation_contexts(openapi, grounding.operations),
        "component_schemas": _component_schemas_for_operations(openapi, grounding.operations),
        "source_refs": grounding.sources,
    }
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    if len(context_json) > max_context_chars:
        context_json = context_json[:max_context_chars] + "\n... truncated ..."

    messages = [
        {
            "role": "system",
            "content": (
                "You are an API assistant embedded in an OpenAPI-powered application. "
                "Answer in the same language as the user's latest question. "
                "Ground your answer only in the provided OpenAPI context. "
                "Mention exact HTTP methods and paths when relevant. "
                "If tools are available, use operation_search to find candidates, operation_get to confirm the exact contract, "
                "then operation_request to execute a real API call when the user asks for live data or an action. "
                "The complete call chain for API execution must be operation_search -> operation_get -> operation_request. "
                "Do not call mutating operations unless the runtime allows them; if blocked, explain the safety policy. "
                "If the OpenAPI context is insufficient, say what is missing instead of inventing details."
            ),
        }
    ]
    for message in request.history[-8:]:
        if message.role in {"user", "assistant"} and message.content.strip():
            messages.append({"role": message.role, "content": message.content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"User question:\n{request.message}\n\n"
                f"Relevant OpenAPI context:\n{context_json}"
            ),
        }
    )
    return messages


def _dump_model(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _operation_contexts(openapi: Dict[str, Any], operations: Iterable[Any]) -> list[Dict[str, Any]]:
    paths = openapi.get("paths") or {}
    contexts = []
    for operation in operations:
        path_item = paths.get(operation.path) or {}
        operation_doc = path_item.get(operation.method.lower()) or {}
        contexts.append(
            {
                "match": _dump_model(operation),
                "openapi_operation": operation_doc,
            }
        )
    return contexts


def _component_schemas_for_operations(
    openapi: Dict[str, Any], operations: Iterable[Any]
) -> Dict[str, Any]:
    schemas = ((openapi.get("components") or {}).get("schemas") or {})
    if not schemas:
        return {}

    paths = openapi.get("paths") or {}
    names: Set[str] = set()
    for operation in operations:
        path_item = paths.get(operation.path) or {}
        _collect_schema_refs(path_item.get(operation.method.lower()) or {}, names)

    previous_size = -1
    while previous_size != len(names):
        previous_size = len(names)
        for name in list(names):
            schema = schemas.get(name)
            if schema:
                _collect_schema_refs(schema, names)

    return {name: schemas[name] for name in sorted(names) if name in schemas}


def _collect_schema_refs(value: Any, names: Set[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            names.add(ref.rsplit("/", 1)[-1])
        for child in value.values():
            _collect_schema_refs(child, names)
    elif isinstance(value, list):
        for child in value:
            _collect_schema_refs(child, names)


def _extract_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    choices = payload.get("choices") or []
    if not choices:
        return {"content": "DeepSeek returned no answer."}
    return choices[0].get("message") or {}


def _message_content(message: Dict[str, Any]) -> str:
    content = message.get("content") or ""
    return content.strip() or "DeepSeek returned an empty answer."


def _assistant_tool_message(message: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.get("content") or "",
        "tool_calls": message.get("tool_calls") or [],
    }


def _tool_call_args(tool_call: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    function = tool_call.get("function") or {}
    name = str(function.get("name") or "")
    raw_args = function.get("arguments") or "{}"
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError:
        args = {"raw": raw_args}
    return name, args if isinstance(args, dict) else {"value": args}


def _tool_result_model(value: Dict[str, Any]) -> AgentToolResult:
    return AgentToolResult(
        tool_name=str(value.get("tool_name") or value.get("toolName") or "tool"),
        ok=value.get("ok") is not False,
        method=value.get("method"),
        path=value.get("path"),
        status=value.get("status"),
        content_type=value.get("content_type") or value.get("contentType"),
        input=value.get("input") if isinstance(value.get("input"), dict) else {},
        data=value.get("data"),
        preview=value.get("preview"),
        error=value.get("error"),
    )


def _tool_definitions() -> list[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "operation_search",
                "description": "Search candidate OpenAPI operations by natural-language query, method, business action, resource, or operationId.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "method": {"type": "string"},
                        "operationId": {"type": "string"},
                        "businessAction": {"type": "string"},
                        "businessResource": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "operation_get",
                "description": "Load the exact OpenAPI contract for one operation before executing it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "description": "OperationId from operation_search."},
                        "operationId": {"type": "string"},
                        "method": {"type": "string"},
                        "path": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "operation_request",
                "description": "Execute a real API request against the host application. Use only after operation_get confirms the contract.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "description": "OperationId to execute."},
                        "pathParams": {"type": "object", "additionalProperties": True},
                        "query": {"type": "object", "additionalProperties": True},
                        "headers": {"type": "object", "additionalProperties": True},
                        "body": {"description": "JSON request body for operations with requestBody."},
                        "responseMode": {"type": "string", "enum": ["short", "full"]},
                    },
                    "required": ["operation"],
                },
            },
        },
    ]


def _fallback_response(grounding: AgentResponse, prefix: str) -> AgentResponse:
    return AgentResponse(
        answer=f"{prefix}\n\nFallback OpenAPI result:\n{grounding.answer}",
        operations=grounding.operations,
        sources=grounding.sources,
    )
