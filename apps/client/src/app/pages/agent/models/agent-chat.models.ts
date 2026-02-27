export const AGENT_SSE_EVENT_TYPES = [
  'thinking',
  'tool_call',
  'tool_result',
  'token',
  'done',
  'error'
] as const;

export type AgentSseEventType = (typeof AGENT_SSE_EVENT_TYPES)[number];

export interface AgentStreamEvent {
  data: Record<string, unknown>;
  event: AgentSseEventType;
}

export interface AgentChatRequest {
  message: string;
  thread_id?: string;
}

export type AgentChatBlockType =
  | 'user'
  | 'assistant'
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'error';

export interface AgentCitation {
  label: string;
  tool_name: string;
  display_name: string;
  field: string;
  value: string;
}

export interface AgentChatBlock {
  args?: Record<string, unknown>;
  citations?: AgentCitation[];
  code?: string;
  confidence?: number | null;
  content?: string;
  error?: string;
  message?: string;
  success?: boolean;
  tool?: string;
  toolsUsed?: number;
  type: AgentChatBlockType;
  verificationCount?: number;
}

export interface AgentChatState {
  activeAssistantIndex: number | null;
  blocks: AgentChatBlock[];
  isStreaming: boolean;
  threadId: string | null;
}

export const INITIAL_AGENT_CHAT_STATE: AgentChatState = {
  activeAssistantIndex: null,
  blocks: [],
  isStreaming: false,
  threadId: null
};

const AGENT_SSE_EVENT_TYPE_SET = new Set<string>(AGENT_SSE_EVENT_TYPES);

export const isAgentSseEventType = (
  eventType: string
): eventType is AgentSseEventType => {
  return AGENT_SSE_EVENT_TYPE_SET.has(eventType);
};
