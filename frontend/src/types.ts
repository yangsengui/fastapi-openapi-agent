export type ThemePreset = "default" | "ocean";
export type Language = "en" | "zh";

export type WidgetConfig = {
  baseUrl: string;
  title: string;
  welcomeTitle: string | null;
  description: string;
  language: Language;
  theme: ThemePreset;
  mode: "floating" | "embedded";
  requestBridge: boolean;
  parentOrigin: string | null;
};

export type Role = "user" | "assistant";

export type OperationHit = {
  method: string;
  path: string;
  operation_id?: string;
  summary?: string;
  parameters?: string[];
  request_body?: boolean;
  responses?: string[];
};

export type ToolResult = {
  tool_name?: string;
  ok?: boolean;
  method?: string;
  path?: string;
  status?: number;
  content_type?: string;
  input?: Record<string, unknown>;
  data?: unknown;
  preview?: string;
  error?: string;
};

export type MessagePart =
  | { type: "text"; id: string; content: string }
  | {
      type: "tool";
      id: string;
      toolCallId: string;
      toolName?: string;
      status: "running" | "done" | "error";
      input?: Record<string, unknown>;
      result?: ToolResult;
    };

export type Message = {
  id: string;
  role: Role;
  content: string;
  parts?: MessagePart[];
  operations?: OperationHit[];
  tool_results?: ToolResult[];
};

export type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
};

export type StreamEvent = {
  type?: string;
  id?: string;
  delta?: string;
  toolCallId?: string;
  toolName?: string;
  input?: Record<string, unknown>;
  output?: ToolResult;
  errorText?: string;
  response?: {
    answer?: string;
    operations?: OperationHit[];
    tool_results?: ToolResult[];
    toolResults?: ToolResult[];
  };
};

export type ChatResponse = {
  answer?: string;
  operations?: OperationHit[];
  tool_results?: ToolResult[];
  toolResults?: ToolResult[];
};

export type ChatHistoryItem = Pick<Message, "role" | "content">;
