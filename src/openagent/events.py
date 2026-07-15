from __future__ import annotations

from typing import Any, Dict, Literal, Union

from pydantic import BaseModel, Field

from .responder import AgentResponse


PYDANTIC_V2 = hasattr(BaseModel, "model_validate")
if PYDANTIC_V2:
    from pydantic import ConfigDict


class AgentEventModel(BaseModel):
    """Base model for events emitted by an Agent backend."""

    type: str

    def to_payload(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump(by_alias=True, exclude_none=True)
        return self.dict(by_alias=True, exclude_none=True)

    if PYDANTIC_V2:
        model_config = ConfigDict(populate_by_name=True)
    else:

        class Config:
            allow_population_by_field_name = True


class AgentStartEvent(AgentEventModel):
    type: Literal["start"] = "start"
    message_id: str = Field(..., alias="messageId")


class TextStartEvent(AgentEventModel):
    type: Literal["text-start"] = "text-start"
    id: str


class TextDeltaEvent(AgentEventModel):
    type: Literal["text-delta"] = "text-delta"
    id: str
    delta: str


class TextEndEvent(AgentEventModel):
    type: Literal["text-end"] = "text-end"
    id: str


class ToolInputStartEvent(AgentEventModel):
    type: Literal["tool-input-start"] = "tool-input-start"
    tool_call_id: str = Field(..., alias="toolCallId")
    tool_name: str = Field(..., alias="toolName")


class ToolInputAvailableEvent(AgentEventModel):
    type: Literal["tool-input-available"] = "tool-input-available"
    tool_call_id: str = Field(..., alias="toolCallId")
    tool_name: str = Field(..., alias="toolName")
    input: Dict[str, Any] = Field(default_factory=dict)


class ToolOutputAvailableEvent(AgentEventModel):
    type: Literal["tool-output-available"] = "tool-output-available"
    tool_call_id: str = Field(..., alias="toolCallId")
    tool_name: str = Field(..., alias="toolName")
    output: Dict[str, Any] = Field(default_factory=dict)


class ToolOutputErrorEvent(AgentEventModel):
    type: Literal["tool-output-error"] = "tool-output-error"
    tool_call_id: str = Field(..., alias="toolCallId")
    tool_name: str = Field(..., alias="toolName")
    output: Dict[str, Any] = Field(default_factory=dict)
    error_text: str = Field(..., alias="errorText")


class AgentFinishEvent(AgentEventModel):
    type: Literal["finish"] = "finish"
    response: AgentResponse


class AgentErrorEvent(AgentEventModel):
    type: Literal["error"] = "error"
    error_text: str = Field(..., alias="errorText")


AgentEvent = Union[
    AgentStartEvent,
    TextStartEvent,
    TextDeltaEvent,
    TextEndEvent,
    ToolInputStartEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
    ToolOutputErrorEvent,
    AgentFinishEvent,
    AgentErrorEvent,
]


def event_payload(event: Union[AgentEventModel, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(event, AgentEventModel):
        return event.to_payload()
    if isinstance(event, dict):
        return event
    raise TypeError(f"Unsupported agent event: {event.__class__.__name__}")
