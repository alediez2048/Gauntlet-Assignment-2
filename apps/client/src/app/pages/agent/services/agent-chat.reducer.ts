import {
  AgentChatState,
  AgentCitation,
  AgentStreamEvent,
  INITIAL_AGENT_CHAT_STATE
} from '../models/agent-chat.models';

const DEFAULT_STREAM_ERROR_MESSAGE =
  'Unable to reach the agent service. Verify it is running and try again.';
const DEFAULT_TOOL_NAME = 'unknown_tool';
const DEFAULT_TOOL_ERROR = 'API_ERROR';
const DEFAULT_SAFE_ERROR_MESSAGE =
  'Received an error from the portfolio service.';

export type AgentChatAction =
  | {
      message: string;
      type: 'start_turn';
    }
  | {
      event: AgentStreamEvent;
      type: 'stream_event';
    }
  | {
      message?: string;
      type: 'stream_error';
    }
  | {
      type: 'cancel_turn';
    }
  | {
      type: 'reset';
    }
  | {
      blockIndex: number;
      rating: 'up' | 'down';
      type: 'set_feedback';
    };

export const reduceAgentChatState = (
  state: AgentChatState = INITIAL_AGENT_CHAT_STATE,
  action: AgentChatAction
): AgentChatState => {
  switch (action.type) {
    case 'start_turn': {
      return {
        ...state,
        activeAssistantIndex: null,
        blocks: [...state.blocks, { content: action.message, type: 'user' }],
        isStreaming: true
      };
    }
    case 'stream_event': {
      return reduceStreamEvent(state, action.event);
    }
    case 'stream_error': {
      return {
        ...state,
        activeAssistantIndex: null,
        blocks: [
          ...state.blocks,
          {
            code: DEFAULT_TOOL_ERROR,
            message: action.message || DEFAULT_STREAM_ERROR_MESSAGE,
            type: 'error'
          }
        ],
        isStreaming: false
      };
    }
    case 'cancel_turn': {
      return {
        ...state,
        activeAssistantIndex: null,
        isStreaming: false
      };
    }
    case 'reset': {
      return INITIAL_AGENT_CHAT_STATE;
    }
    case 'set_feedback': {
      const blocks = [...state.blocks];
      const target = blocks[action.blockIndex];
      if (target) {
        blocks[action.blockIndex] = { ...target, feedback: action.rating };
      }
      return { ...state, blocks };
    }
    default: {
      return state;
    }
  }
};

const reduceStreamEvent = (
  state: AgentChatState,
  event: AgentStreamEvent
): AgentChatState => {
  const blocks = [...state.blocks];

  switch (event.event) {
    case 'thinking': {
      blocks.push({
        message:
          readString(event.data['message']) || 'Analyzing your request...',
        type: 'thinking'
      });

      return {
        ...state,
        blocks
      };
    }
    case 'tool_call': {
      blocks.push({
        args: readRecord(event.data['args']),
        tool: readString(event.data['tool']) || DEFAULT_TOOL_NAME,
        type: 'tool_call'
      });

      return {
        ...state,
        blocks
      };
    }
    case 'tool_result': {
      blocks.push({
        error: readString(event.data['error']) || undefined,
        success: Boolean(event.data['success']),
        tool: readString(event.data['tool']) || DEFAULT_TOOL_NAME,
        type: 'tool_result'
      });

      return {
        ...state,
        blocks
      };
    }
    case 'token': {
      const tokenContent = readString(event.data['content']);
      if (!tokenContent) {
        return state;
      }

      if (state.activeAssistantIndex === null) {
        blocks.push({ content: tokenContent, type: 'assistant' });

        return {
          ...state,
          activeAssistantIndex: blocks.length - 1,
          blocks
        };
      }

      const assistantBlock = blocks[state.activeAssistantIndex];
      const currentContent = assistantBlock?.content || '';

      blocks[state.activeAssistantIndex] = {
        ...assistantBlock,
        content: `${currentContent}${tokenContent}`,
        type: 'assistant'
      };

      return {
        ...state,
        blocks
      };
    }
    case 'done': {
      const threadId = readString(event.data['thread_id']) || state.threadId;
      const response = readRecord(event.data['response']);
      const message = readString(response['message']);
      const citations: AgentCitation[] = Array.isArray(response['citations'])
        ? (response['citations'] as AgentCitation[])
        : [];
      const confidence =
        typeof response['confidence'] === 'number'
          ? (response['confidence'] as number)
          : null;

      const toolCallHistory = Array.isArray(event.data['tool_call_history'])
        ? (event.data['tool_call_history'] as unknown[])
        : [];
      const toolsUsed = toolCallHistory.length;
      const verificationCount =
        typeof event.data['verification_count'] === 'number'
          ? (event.data['verification_count'] as number)
          : undefined;

      if (message) {
        if (state.activeAssistantIndex === null) {
          blocks.push({
            citations,
            confidence,
            content: message,
            toolsUsed,
            type: 'assistant',
            verificationCount
          });
        } else {
          const assistantBlock = blocks[state.activeAssistantIndex];
          if (!assistantBlock?.content) {
            blocks[state.activeAssistantIndex] = {
              ...assistantBlock,
              citations,
              confidence,
              content: message,
              toolsUsed,
              type: 'assistant',
              verificationCount
            };
          } else {
            blocks[state.activeAssistantIndex] = {
              ...assistantBlock,
              citations,
              confidence,
              toolsUsed,
              verificationCount
            };
          }
        }
      }

      return {
        ...state,
        activeAssistantIndex: null,
        blocks,
        isStreaming: false,
        threadId
      };
    }
    case 'error': {
      const code = readString(event.data['code']) || DEFAULT_TOOL_ERROR;
      const message =
        readString(event.data['message']) || DEFAULT_SAFE_ERROR_MESSAGE;

      blocks.push({
        code,
        message,
        type: 'error'
      });

      return {
        ...state,
        activeAssistantIndex: null,
        blocks,
        isStreaming: false
      };
    }
    default: {
      return state;
    }
  }
};

const readString = (value: unknown): string => {
  return typeof value === 'string' ? value : '';
};

const readRecord = (value: unknown): Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
};
