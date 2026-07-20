from __future__ import annotations

import json
import os
import secrets
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

from .catalog import OperationCatalog, OperationMetadata
from .i18n import Language, translate, validate_language
from .responder import (
    AgentRequest,
    AgentResponse,
    AgentToolResult,
    default_openapi_responder,
)
from .runtime import OpenAPIAgentRuntime

Responder = Callable[[AgentRequest, Dict[str, Any]], Awaitable[AgentResponse]]
ToolRunner = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
Completion = Callable[..., Awaitable[Any]]


class LiteLLMNotInstalledError(RuntimeError):
    pass


async def stream_llm_agent(
    request: AgentRequest,
    openapi: Dict[str, Any],
    tool_runner: ToolRunner,
    model: Optional[str] = None,
    *,
    language: Language = "en",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: float = 30.0,
    max_context_chars: int = 16000,
    max_tool_rounds: int = 6,
    model_kwargs: Optional[Dict[str, Any]] = None,
    completion: Optional[Completion] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream a LiteLLM-backed tool-calling run as UI-friendly events."""

    language = validate_language(language)

    try:
        resolved_model = _resolve_model(model, language)
    except RuntimeError as exc:
        yield {"type": "error", "errorText": str(exc)}
        return

    grounding = default_openapi_responder(request, openapi, language)
    messages: list[dict[str, Any]] = _build_messages(
        request, openapi, max_context_chars, language
    )
    tool_results: list[Dict[str, Any]] = []
    final_text_parts: list[str] = []
    active_text_id: Optional[str] = None
    text_part_index = 0
    run_completion = completion or _litellm_completion

    yield {"type": "start", "messageId": _stream_id("assistant")}

    for round_index in range(max(1, max_tool_rounds)):
        tool_call_state: dict[int, dict[str, Any]] = {}
        round_text_parts: list[str] = []
        try:
            response = await run_completion(
                **_completion_params(
                    model=resolved_model,
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    timeout=timeout,
                    stream=True,
                    model_kwargs=model_kwargs,
                )
            )
            async for raw_chunk in response:
                chunk = _response_dict(raw_chunk)
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if content:
                    text = str(content)
                    if active_text_id is None:
                        text_part_index += 1
                        active_text_id = f"text-{text_part_index}"
                        yield {"type": "text-start", "id": active_text_id}
                    round_text_parts.append(text)
                    final_text_parts.append(text)
                    yield {"type": "text-delta", "id": active_text_id, "delta": text}

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
                        fn_state["name"] = str(fn_state.get("name") or "") + str(
                            fn_delta["name"]
                        )
                    if fn_delta.get("arguments"):
                        fn_state["arguments"] = str(fn_state.get("arguments") or "") + str(
                            fn_delta["arguments"]
                        )
        except Exception as exc:
            if active_text_id is not None:
                yield {"type": "text-end", "id": active_text_id}
                active_text_id = None
            yield {"type": "error", "errorText": _request_error(exc, language)}
            return

        tool_calls = [tool_call_state[index] for index in sorted(tool_call_state)]
        if not tool_calls:
            if active_text_id is not None:
                yield {"type": "text-end", "id": active_text_id}
            yield {
                "type": "finish",
                "response": _agent_response_payload(
                    grounding, "".join(final_text_parts), tool_results, language
                ),
            }
            return

        if active_text_id is not None:
            yield {"type": "text-end", "id": active_text_id}
            active_text_id = None
        for index, tool_call in enumerate(tool_calls):
            if not tool_call.get("id"):
                tool_call["id"] = f"tool-{round_index}-{index}"
        messages.append(
            {
                "role": "assistant",
                "content": "".join(round_text_parts),
                "tool_calls": tool_calls,
            }
        )
        for index, tool_call in enumerate(tool_calls):
            name, args = _tool_call_args(tool_call)
            tool_call_id = str(tool_call.get("id") or name or f"tool-{round_index}-{index}")
            yield {
                "type": "tool-input-start",
                "toolCallId": tool_call_id,
                "toolName": name,
            }
            yield {
                "type": "tool-input-available",
                "toolCallId": tool_call_id,
                "toolName": name,
                "input": args,
            }
            try:
                result = await tool_runner(name, args)
            except Exception as exc:
                error_text = translate(
                    language, "tool_failed", error_type=exc.__class__.__name__
                )
                yield {
                    "type": "tool-output-error",
                    "toolCallId": tool_call_id,
                    "toolName": name,
                    "output": {},
                    "errorText": error_text,
                }
                yield {"type": "error", "errorText": error_text}
                return
            tool_results.append(result)
            if result.get("ok") is False:
                yield {
                    "type": "tool-output-error",
                    "toolCallId": tool_call_id,
                    "toolName": name,
                    "output": result,
                    "errorText": str(
                        result.get("error")
                        or result.get("preview")
                        or translate(language, "tool_failed_generic")
                    ),
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

    yield {
        "type": "error",
        "errorText": translate(language, "max_rounds"),
    }


def create_llm_responder(
    model: Optional[str] = None,
    *,
    language: Language = "en",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: float = 30.0,
    max_context_chars: int = 16000,
    tool_runner: Optional[ToolRunner] = None,
    max_tool_rounds: int = 4,
    model_kwargs: Optional[Dict[str, Any]] = None,
    completion: Optional[Completion] = None,
) -> Responder:
    """Create a provider-neutral responder backed by LiteLLM."""

    language = validate_language(language)
    resolved_model = _resolve_model(model, language)
    run_completion = completion or _litellm_completion

    async def responder(request: AgentRequest, openapi: Dict[str, Any]) -> AgentResponse:
        grounding = default_openapi_responder(request, openapi, language)
        messages = _build_messages(request, openapi, max_context_chars, language)
        tool_results: list[Dict[str, Any]] = []
        resolved_tool_runner = tool_runner
        if resolved_tool_runner is None:
            resolved_tool_runner = OpenAPIAgentRuntime(
                openapi,
                enable_api_calls=False,
                language=language,
            ).run_tool

        try:
            for round_index in range(max(1, max_tool_rounds)):
                response = await run_completion(
                    **_completion_params(
                        model=resolved_model,
                        messages=messages,
                        api_key=api_key,
                        base_url=base_url,
                        temperature=temperature,
                        timeout=timeout,
                        stream=False,
                        model_kwargs=model_kwargs,
                    )
                )
                message = _extract_message(_response_dict(response), language)
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    return AgentResponse(
                        answer=_message_content(message, language),
                        operations=grounding.operations,
                        sources=grounding.sources,
                        tool_results=[_tool_result_model(item) for item in tool_results],
                    )

                for index, tool_call in enumerate(tool_calls):
                    if not tool_call.get("id"):
                        tool_call["id"] = f"tool-{round_index}-{index}"
                messages.append(_assistant_tool_message(message))
                for tool_call in tool_calls:
                    name, args = _tool_call_args(tool_call)
                    result = await resolved_tool_runner(name, args)
                    tool_results.append(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": str(tool_call.get("id") or name),
                            "name": name,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    )

            return AgentResponse(
                answer=translate(language, "max_rounds"),
                operations=grounding.operations,
                sources=grounding.sources,
                tool_results=[_tool_result_model(item) for item in tool_results],
            )
        except Exception as exc:
            return _fallback_response(grounding, _request_error(exc, language), language)

    return responder


async def _litellm_completion(**kwargs: Any) -> Any:
    try:
        from litellm import acompletion
    except ImportError as exc:
        raise LiteLLMNotInstalledError(
            'LiteLLM is not installed. Install "fastapi-openapi-agent[llm]".'
        ) from exc
    return await acompletion(**kwargs)


def _resolve_model(model: Optional[str], language: Language = "en") -> str:
    resolved = model or os.getenv("OPENAGENT_MODEL")
    if not resolved:
        raise RuntimeError(translate(language, "llm_not_configured"))
    if "/" not in resolved:
        resolved = f"deepseek/{resolved}"
    return resolved


def _completion_params(
    *,
    model: str,
    messages: list[dict[str, Any]],
    api_key: Optional[str],
    base_url: Optional[str],
    temperature: Optional[float],
    timeout: float,
    stream: bool,
    model_kwargs: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    params = dict(model_kwargs or {})
    params.update(
        {
            "model": model,
            "messages": messages,
            "tools": _tool_definitions(),
            "timeout": timeout,
            "stream": stream,
        }
    )
    if temperature is not None:
        params["temperature"] = temperature

    resolved_api_key = api_key or os.getenv("OPENAGENT_API_KEY")
    resolved_base_url = base_url or os.getenv("OPENAGENT_BASE_URL")
    if resolved_api_key:
        params["api_key"] = resolved_api_key
    if resolved_base_url:
        params["base_url"] = resolved_base_url
    return params


def _response_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        result = value.model_dump()
    elif hasattr(value, "dict"):
        result = value.dict()
    else:
        raise TypeError(f"Unsupported LiteLLM response type: {value.__class__.__name__}")
    if not isinstance(result, dict):
        raise TypeError(f"Unsupported LiteLLM response payload: {result.__class__.__name__}")
    return result


def _request_error(exc: Exception, language: Language = "en") -> str:
    if isinstance(exc, LiteLLMNotInstalledError):
        return translate(language, "litellm_missing")
    status_code = getattr(exc, "status_code", None)
    if status_code:
        return translate(language, "llm_http_error", status=status_code)
    return translate(language, "llm_error", error_type=exc.__class__.__name__)


def _agent_response_payload(
    grounding: AgentResponse,
    answer: str,
    tool_results: list[Dict[str, Any]],
    language: Language = "en",
) -> Dict[str, Any]:
    response = AgentResponse(
        answer=answer or translate(language, "empty_answer"),
        operations=grounding.operations,
        sources=grounding.sources,
        tool_results=[_tool_result_model(item) for item in tool_results],
    )
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


def _stream_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _build_messages(
    request: AgentRequest,
    openapi: Dict[str, Any],
    max_context_chars: int,
    language: Language = "en",
) -> list[dict[str, str]]:
    operations = [
        _dump_operation_metadata(operation)
        for operation in OperationCatalog.from_openapi(openapi).list_operations()
    ]
    context_json = _operation_context_json(openapi, operations, max_context_chars)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an API assistant embedded in an OpenAPI-powered application. "
                f"Always answer in {'English' if language == 'en' else 'Simplified Chinese'}, "
                "regardless of the language used in the question or API schema. "
                "The provided OpenAPI context contains operation metadata and intentionally contains no schemas. "
                "catalogComplete says whether every operation fit in the context; use operation_search when it is false. "
                "Ground operation selection only in this context and tool results. "
                "Mention exact HTTP methods and paths when relevant. "
                "Select an operationId from the catalog, then use operation_get to load its exact parameters and schemas. "
                "If operationId is absent, identify the operation with its method and path instead. "
                "Use operation_request only after operation_get and only when the user asks for live data or an action. "
                "The required call chain for API execution is operation_get -> operation_request. "
                "operation_search is optional and only useful for filtering a large catalog; it never replaces operation_get. "
                "Do not call mutating operations unless the runtime allows them; if blocked, explain the safety policy. "
                "Never infer request or response schemas from metadata; call operation_get instead. "
                "If the loaded contract is insufficient, say what is missing instead of inventing details."
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


def _dump_operation_metadata(operation: OperationMetadata) -> Dict[str, Any]:
    return {
        "operationId": operation.operation_id,
        "method": operation.method,
        "path": operation.path,
        "summary": operation.summary,
        "description": operation.description,
        "tags": operation.tags,
        "parameters": operation.parameters,
        "requestBody": operation.request_body,
        "responses": operation.responses,
    }


def _operation_context_json(
    openapi: Dict[str, Any],
    operations: list[Dict[str, Any]],
    max_context_chars: int,
) -> str:
    budget = max(256, int(max_context_chars))
    candidates = [
        {
            "catalogComplete": True,
            "api": openapi.get("info") or {},
            "servers": openapi.get("servers") or [],
            "operations": operations,
        },
        {"catalogComplete": True, "operations": operations},
        {
            "catalogComplete": True,
            "operations": [_compact_operation(operation) for operation in operations],
        },
    ]
    for candidate in candidates:
        encoded = _compact_json(candidate)
        if len(encoded) <= budget:
            return encoded

    partial: Dict[str, Any] = {
        "catalogComplete": False,
        "totalOperations": len(operations),
        "operations": [],
    }
    for operation in operations:
        partial["operations"].append(_operation_identity(operation))
        encoded = _compact_json(partial)
        if len(encoded) > budget:
            partial["operations"].pop()
            break
    return _compact_json(partial)


def _compact_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "operationId": operation.get("operationId"),
        "method": operation.get("method"),
        "path": operation.get("path"),
        "summary": _truncate(operation.get("summary"), 120),
        "description": _truncate(operation.get("description"), 240),
        "tags": list(operation.get("tags") or [])[:8],
        "parameters": list(operation.get("parameters") or [])[:12],
        "requestBody": bool(operation.get("requestBody")),
        "responses": list(operation.get("responses") or [])[:10],
    }


def _operation_identity(operation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "operationId": operation.get("operationId"),
        "method": operation.get("method"),
        "path": operation.get("path"),
        "summary": _truncate(operation.get("summary"), 80),
    }


def _truncate(value: Any, limit: int) -> Any:
    if not isinstance(value, str) or len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _extract_message(
    payload: Dict[str, Any], language: Language = "en"
) -> Dict[str, Any]:
    choices = payload.get("choices") or []
    if not choices:
        return {"content": translate(language, "no_answer")}
    return choices[0].get("message") or {}


def _message_content(message: Dict[str, Any], language: Language = "en") -> str:
    content = message.get("content") or ""
    return str(content).strip() or translate(language, "empty_answer")


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
                        "operationId": {
                            "type": "string",
                            "description": "OperationId selected from the metadata catalog.",
                        },
                        "method": {
                            "type": "string",
                            "description": "HTTP method when operationId is absent.",
                        },
                        "path": {
                            "type": "string",
                            "description": "OpenAPI path when operationId is absent.",
                        },
                    },
                    "anyOf": [
                        {"required": ["operationId"]},
                        {"required": ["method", "path"]},
                    ],
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
                        "operationId": {
                            "type": "string",
                            "description": "OperationId previously loaded with operation_get.",
                        },
                        "method": {
                            "type": "string",
                            "description": "Previously loaded HTTP method when operationId is absent.",
                        },
                        "path": {
                            "type": "string",
                            "description": "Previously loaded OpenAPI path when operationId is absent.",
                        },
                        "pathParams": {"type": "object", "additionalProperties": True},
                        "query": {"type": "object", "additionalProperties": True},
                        "headers": {"type": "object", "additionalProperties": True},
                        "body": {"description": "JSON request body for operations with requestBody."},
                        "responseMode": {"type": "string", "enum": ["short", "full"]},
                    },
                    "anyOf": [
                        {"required": ["operationId"]},
                        {"required": ["method", "path"]},
                    ],
                },
            },
        },
    ]


def _fallback_response(
    grounding: AgentResponse, prefix: str, language: Language = "en"
) -> AgentResponse:
    return AgentResponse(
        answer=f"{prefix}\n\n{translate(language, 'fallback_heading')}\n{grounding.answer}",
        operations=grounding.operations,
        sources=grounding.sources,
    )
