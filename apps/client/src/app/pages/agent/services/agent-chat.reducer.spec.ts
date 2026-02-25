import { INITIAL_AGENT_CHAT_STATE } from '../models/agent-chat.models';
import { reduceAgentChatState } from './agent-chat.reducer';

describe('agent-chat.reducer', () => {
  it('starts a turn, accumulates tokens, and finalizes on done', () => {
    let state = reduceAgentChatState(INITIAL_AGENT_CHAT_STATE, {
      message: 'How is my portfolio doing ytd?',
      type: 'start_turn'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: { message: 'Analyzing your request...' },
        event: 'thinking'
      },
      type: 'stream_event'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: { content: 'Portfolio net performance is ' },
        event: 'token'
      },
      type: 'stream_event'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: { content: '8.12%.' },
        event: 'token'
      },
      type: 'stream_event'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: {
          response: { message: 'Portfolio net performance is 8.12%.' },
          thread_id: 'thread-123'
        },
        event: 'done'
      },
      type: 'stream_event'
    });

    const assistantBlock = state.blocks.find(
      (block) => block.type === 'assistant'
    );

    expect(state.isStreaming).toBe(false);
    expect(state.threadId).toBe('thread-123');
    expect(assistantBlock?.content).toBe('Portfolio net performance is 8.12%.');
  });

  it('stores tool telemetry blocks from call and result events', () => {
    let state = reduceAgentChatState(INITIAL_AGENT_CHAT_STATE, {
      message: 'Run a portfolio analysis',
      type: 'start_turn'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: {
          args: { time_period: 'ytd' },
          tool: 'analyze_portfolio_performance'
        },
        event: 'tool_call'
      },
      type: 'stream_event'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: { success: true, tool: 'analyze_portfolio_performance' },
        event: 'tool_result'
      },
      type: 'stream_event'
    });

    expect(state.blocks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          args: { time_period: 'ytd' },
          tool: 'analyze_portfolio_performance',
          type: 'tool_call'
        }),
        expect.objectContaining({
          success: true,
          tool: 'analyze_portfolio_performance',
          type: 'tool_result'
        })
      ])
    );
  });

  it('ends the stream safely on error events', () => {
    let state = reduceAgentChatState(INITIAL_AGENT_CHAT_STATE, {
      message: 'What is my risk profile?',
      type: 'start_turn'
    });

    state = reduceAgentChatState(state, {
      event: {
        data: {
          code: 'API_ERROR',
          message: 'Received an error from the portfolio service.'
        },
        event: 'error'
      },
      type: 'stream_event'
    });

    const errorBlock = state.blocks.find((block) => block.type === 'error');

    expect(state.isStreaming).toBe(false);
    expect(errorBlock?.code).toBe('API_ERROR');
    expect(errorBlock?.message).toBe(
      'Received an error from the portfolio service.'
    );
  });
});
