import type { Language } from "../types";

const translations = {
  en: {
    toggleHistory: "Toggle history",
    newChat: "New chat",
    closeSidebar: "Close sidebar",
    closeHistory: "Close history",
    conversations: "Conversations",
    noConversations: "No conversations yet.",
    message: "Message",
    sending: "Sending",
    sendMessage: "Send message",
    composerPlaceholder: "Ask about the API, or ask the agent to call an endpoint...",
    thinking: "Thinking...",
    preparing: "Preparing",
    calling: "Calling",
    called: "Called",
    tool: "tool",
    toolFailed: "Tool execution failed",
    streamFailed: "Stream failed.",
    noAnswer: "No answer returned.",
    newChatTitle: "New chat",
    greetings: ["Good morning", "Good afternoon", "Good evening"],
    justNow: "just now",
    minutesAgo: (value: number) => `${value}m ago`,
    hoursAgo: (value: number) => `${value}h ago`,
    prompts: [
      "What can you help me with?",
      "Any bright ideas?",
      "Help me generate a report from the data",
    ],
  },
  zh: {
    toggleHistory: "打开或关闭历史记录",
    newChat: "新对话",
    closeSidebar: "关闭侧栏",
    closeHistory: "关闭历史记录",
    conversations: "对话记录",
    noConversations: "暂无对话。",
    message: "消息",
    sending: "正在发送",
    sendMessage: "发送消息",
    composerPlaceholder: "询问 API 相关问题，或让助手调用接口……",
    thinking: "思考中……",
    preparing: "正在准备",
    calling: "正在调用",
    called: "已调用",
    tool: "工具",
    toolFailed: "工具执行失败",
    streamFailed: "流式请求失败。",
    noAnswer: "未返回回答。",
    newChatTitle: "新对话",
    greetings: ["早上好", "下午好", "晚上好"],
    justNow: "刚刚",
    minutesAgo: (value: number) => `${value} 分钟前`,
    hoursAgo: (value: number) => `${value} 小时前`,
    prompts: [
      "你能帮我做什么？",
      "灵光一线？",
      "帮我为数据生成报告",
    ],
  },
} as const;

export type UiCopy = (typeof translations)[Language];

export function getCopy(language: Language): UiCopy {
  return translations[language];
}
