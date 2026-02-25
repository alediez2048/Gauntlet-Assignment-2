import {
  AgentStreamEvent,
  isAgentSseEventType
} from '../models/agent-chat.models';

export interface AgentSseParserState {
  buffer: string;
}

export interface AgentSseChunkParseResult {
  events: AgentStreamEvent[];
  state: AgentSseParserState;
}

export const createAgentSseParserState = (): AgentSseParserState => {
  return { buffer: '' };
};

export const parseAgentSseChunk = (
  chunk: string,
  state: AgentSseParserState
): AgentSseChunkParseResult => {
  const combinedBuffer = `${state.buffer}${chunk}`.replace(/\r\n/g, '\n');
  const eventFrames = combinedBuffer.split('\n\n');
  const incompleteFrame = eventFrames.pop() ?? '';
  const events = eventFrames
    .map((frame) => parseSseFrame(frame))
    .filter((event): event is AgentStreamEvent => event !== null);

  return {
    events,
    state: { buffer: incompleteFrame }
  };
};

export const flushAgentSseParserState = (
  state: AgentSseParserState
): AgentSseChunkParseResult => {
  return parseAgentSseChunk('\n\n', state);
};

const parseSseFrame = (frame: string): AgentStreamEvent | null => {
  if (!frame.trim()) {
    return null;
  }

  let eventType = '';
  const dataLines: string[] = [];

  for (const rawLine of frame.split('\n')) {
    const line = rawLine.trim();

    if (!line || line.startsWith(':')) {
      continue;
    }

    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!eventType || dataLines.length === 0 || !isAgentSseEventType(eventType)) {
    return null;
  }

  try {
    const data = JSON.parse(dataLines.join('\n'));
    if (!isPlainObject(data)) {
      return null;
    }

    return { data, event: eventType };
  } catch {
    return null;
  }
};

const isPlainObject = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};
