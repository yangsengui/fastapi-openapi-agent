from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict

from .catalog import OperationCatalog
from .events import (
    AgentEvent,
    AgentFinishEvent,
    AgentStartEvent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
)
from .responder import AgentRequest, AgentResponse
from .runtime import OpenAPIAgentRuntime


@dataclass(frozen=True)
class AgentContext:
    """Per-run SDK context exposed to custom Agent backends."""

    request: AgentRequest
    openapi: Dict[str, Any]
    catalog: OperationCatalog
    runtime: OpenAPIAgentRuntime

    async def run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return await self.runtime.run_tool(name, args)


class AgentBackend:
    """Base class for custom Agent implementations.

    Implement ``respond`` for JSON responses. Override ``stream`` when the
    backend can emit incremental text or tool events. The default stream
    implementation converts ``respond`` into the standard event protocol.
    """

    async def respond(self, context: AgentContext) -> AgentResponse:
        raise NotImplementedError

    async def stream(self, context: AgentContext) -> AsyncIterator[AgentEvent]:
        message_id = f"assistant_{secrets.token_hex(6)}"
        text_id = "text-1"
        yield AgentStartEvent(messageId=message_id)
        response = await self.respond(context)
        yield TextStartEvent(id=text_id)
        yield TextDeltaEvent(id=text_id, delta=response.answer)
        yield TextEndEvent(id=text_id)
        yield AgentFinishEvent(response=response)


class OpenAPIAgent:
    """Framework-neutral entry point for a custom OpenAPI Agent backend."""

    def __init__(self, backend: AgentBackend) -> None:
        self.backend = backend

    def create_context(
        self,
        request: AgentRequest,
        openapi: Dict[str, Any],
        runtime: OpenAPIAgentRuntime,
    ) -> AgentContext:
        return AgentContext(
            request=request,
            openapi=openapi,
            catalog=runtime.catalog,
            runtime=runtime,
        )

    async def respond(
        self,
        request: AgentRequest,
        openapi: Dict[str, Any],
        runtime: OpenAPIAgentRuntime,
    ) -> AgentResponse:
        return await self.backend.respond(self.create_context(request, openapi, runtime))

    async def stream(
        self,
        request: AgentRequest,
        openapi: Dict[str, Any],
        runtime: OpenAPIAgentRuntime,
    ) -> AsyncIterator[AgentEvent]:
        context = self.create_context(request, openapi, runtime)
        async for event in self.backend.stream(context):
            yield event
