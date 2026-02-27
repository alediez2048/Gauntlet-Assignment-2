import {
  EvalStreamEvent,
  isEvalSseEventType
} from '../models/agent-chat.models';

export interface EvalSseParserState {
  buffer: string;
}

export interface EvalSseChunkParseResult {
  events: EvalStreamEvent[];
  state: EvalSseParserState;
}

export const createEvalSseParserState = (): EvalSseParserState => {
  return { buffer: '' };
};

export const parseEvalSseChunk = (
  chunk: string,
  state: EvalSseParserState
): EvalSseChunkParseResult => {
  const combinedBuffer = `${state.buffer}${chunk}`.replace(/\r\n/g, '\n');
  const eventFrames = combinedBuffer.split('\n\n');
  const incompleteFrame = eventFrames.pop() ?? '';
  const events = eventFrames
    .map((frame) => parseEvalSseFrame(frame))
    .filter((event): event is EvalStreamEvent => event !== null);

  return {
    events,
    state: { buffer: incompleteFrame }
  };
};

export const flushEvalSseParserState = (
  state: EvalSseParserState
): EvalSseChunkParseResult => {
  return parseEvalSseChunk('\n\n', state);
};

const parseEvalSseFrame = (frame: string): EvalStreamEvent | null => {
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

  if (!eventType || dataLines.length === 0 || !isEvalSseEventType(eventType)) {
    return null;
  }

  try {
    const data = JSON.parse(dataLines.join('\n'));
    if (typeof data !== 'object' || data === null || Array.isArray(data)) {
      return null;
    }

    return { data, event: eventType };
  } catch {
    return null;
  }
};
