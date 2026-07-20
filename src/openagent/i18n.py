from __future__ import annotations

from typing import Dict, Literal

Language = Literal["en", "zh"]
SUPPORTED_LANGUAGES = ("en", "zh")

DEFAULT_DESCRIPTIONS: Dict[Language, str] = {
    "en": "Ask questions about this service's OpenAPI schema.",
    "zh": "询问有关此服务 OpenAPI 接口的问题。",
}

MESSAGES: Dict[Language, Dict[str, str]] = {
    "en": {
        "no_operations": "I could not find any operations in the OpenAPI schema.",
        "this_api": "this API",
        "answer_intro": "Based on {title}'s OpenAPI schema, these endpoints look most relevant to: {message}",
        "no_summary": "No summary",
        "params": "params: {value}",
        "request_body": "request body",
        "responses": "responses: {value}",
        "production_hint": "For production use, pass a custom responder that calls your LLM and uses the same OpenAPI schema as tool context.",
        "found_operations": "Found {count} operation(s).",
        "loaded_contract": "Loaded contract for {method} {path}.",
        "unknown_tool": "Unknown tool: {name}",
        "api_calls_disabled": "API calls are disabled for this agent.",
        "invoker_required": "API calls require an operation invoker.",
        "operation_not_found": "Operation not found.",
        "contract_required": "Operation contract must be loaded with operation_get before execution.",
        "internal_route": "Agent internal routes cannot be called.",
        "blocked_mutation": "Blocked {method} {path}: mutating API calls are disabled.",
        "mutation_requires_flag": "Mutating API calls require allow_mutating_api_calls=True.",
        "missing_path_param": "Missing required path parameter: {name}",
        "internal_request_failed": "Internal API request failed: {error_type}.",
        "tool_failed": "Tool execution failed: {error_type}.",
        "tool_failed_generic": "Tool execution failed",
        "max_rounds": "The agent reached the maximum tool-calling rounds before producing a final answer.",
        "empty_answer": "The model returned an empty answer.",
        "no_answer": "The model returned no answer.",
        "llm_http_error": "LLM request failed with HTTP {status}.",
        "llm_error": "LLM request failed: {error_type}.",
        "llm_not_configured": "OPENAGENT_MODEL is not set and no model was configured.",
        "litellm_missing": "LiteLLM is not installed. Install \"fastapi-openapi-agent[llm]\".",
        "fallback_heading": "Fallback OpenAPI result:",
    },
    "zh": {
        "no_operations": "在 OpenAPI 文档中没有找到任何接口。",
        "this_api": "此 API",
        "answer_intro": "根据 {title} 的 OpenAPI 文档，以下接口与“{message}”最相关：",
        "no_summary": "暂无说明",
        "params": "参数：{value}",
        "request_body": "请求体",
        "responses": "响应：{value}",
        "production_hint": "在生产环境中，可传入自定义 responder，调用你的大模型并使用同一份 OpenAPI 文档作为工具上下文。",
        "found_operations": "找到 {count} 个接口。",
        "loaded_contract": "已加载 {method} {path} 的接口定义。",
        "unknown_tool": "未知工具：{name}",
        "api_calls_disabled": "此智能助手已禁用 API 调用。",
        "invoker_required": "API 调用需要配置接口调用器。",
        "operation_not_found": "未找到接口。",
        "contract_required": "执行前必须先通过 operation_get 加载接口定义。",
        "internal_route": "不能调用智能助手的内部路由。",
        "blocked_mutation": "已阻止 {method} {path}：修改类 API 调用未启用。",
        "mutation_requires_flag": "修改类 API 调用需要设置 allow_mutating_api_calls=True。",
        "missing_path_param": "缺少必填路径参数：{name}",
        "internal_request_failed": "内部 API 请求失败：{error_type}。",
        "tool_failed": "工具执行失败：{error_type}。",
        "tool_failed_generic": "工具执行失败",
        "max_rounds": "智能助手在生成最终回答前已达到工具调用轮次上限。",
        "empty_answer": "模型返回了空回答。",
        "no_answer": "模型未返回回答。",
        "llm_http_error": "大模型请求失败，HTTP 状态码为 {status}。",
        "llm_error": "大模型请求失败：{error_type}。",
        "llm_not_configured": "未设置 OPENAGENT_MODEL，也未配置模型。",
        "litellm_missing": "尚未安装 LiteLLM，请安装 \"fastapi-openapi-agent[llm]\"。",
        "fallback_heading": "OpenAPI 后备结果：",
    },
}


def validate_language(language: str) -> Language:
    if language not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise ValueError(f"Unsupported language {language!r}. Expected one of: {supported}.")
    return language  # type: ignore[return-value]


def translate(language: Language, key: str, **values: object) -> str:
    return MESSAGES[language][key].format(**values)
