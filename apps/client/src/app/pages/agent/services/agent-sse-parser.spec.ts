import {
  createAgentSseParserState,
  flushAgentSseParserState,
  parseAgentSseChunk
} from './agent-sse-parser';

describe('agent-sse-parser', () => {
  it('parses complete typed SSE frames', () => {
    const initialState = createAgentSseParserState();
    const chunk = [
      'event: thinking',
      'data: {"message":"Analyzing your request..."}',
      '',
      'event: token',
      'data: {"content":"Hello"}',
      '',
      ''
    ].join('\n');

    const result = parseAgentSseChunk(chunk, initialState);

    expect(result.events).toEqual([
      {
        event: 'thinking',
        data: { message: 'Analyzing your request...' }
      },
      {
        event: 'token',
        data: { content: 'Hello' }
      }
    ]);
    expect(result.state.buffer).toBe('');
  });

  it('buffers incomplete event frames across chunk boundaries', () => {
    const firstResult = parseAgentSseChunk(
      'event: token\ndata: {"content":"Hel',
      createAgentSseParserState()
    );

    expect(firstResult.events).toEqual([]);
    expect(firstResult.state.buffer).toContain('"Hel');

    const secondResult = parseAgentSseChunk('lo"}\n\n', firstResult.state);

    expect(secondResult.events).toEqual([
      {
        event: 'token',
        data: { content: 'Hello' }
      }
    ]);
    expect(secondResult.state.buffer).toBe('');
  });

  it('ignores unknown and malformed events safely', () => {
    const unknownEventChunk = [
      'event: unknown',
      'data: {"x":1}',
      '',
      'event: token',
      'data: {"content": "ok"',
      ''
    ].join('\n');

    const intermediate = parseAgentSseChunk(
      unknownEventChunk,
      createAgentSseParserState()
    );
    const flushed = flushAgentSseParserState(intermediate.state);

    expect(intermediate.events).toEqual([]);
    expect(flushed.events).toEqual([]);
  });
});
