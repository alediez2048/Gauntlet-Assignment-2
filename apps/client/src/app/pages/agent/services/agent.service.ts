import { TokenStorageService } from '@ghostfolio/client/services/token-storage.service';
import { HEADER_KEY_TOKEN } from '@ghostfolio/common/config';

import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AgentChatRequest,
  AgentStreamEvent
} from '../models/agent-chat.models';
import { AGENT_ENDPOINT_CONFIG } from './agent-endpoint.config';
import {
  createAgentSseParserState,
  flushAgentSseParserState,
  parseAgentSseChunk
} from './agent-sse-parser';

const DEFAULT_ERROR_MESSAGE =
  'Unable to reach the agent service. Verify it is running and try again.';

@Injectable({
  providedIn: 'root'
})
export class AgentService {
  private readonly agentEndpointConfig = inject(AGENT_ENDPOINT_CONFIG);
  private readonly tokenStorageService = inject(TokenStorageService);

  public streamChat(request: AgentChatRequest): Observable<AgentStreamEvent> {
    return new Observable<AgentStreamEvent>((subscriber) => {
      const abortController = new AbortController();

      const run = async () => {
        try {
          const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream'
          };
          const token = this.tokenStorageService.getToken();
          if (token) {
            headers[HEADER_KEY_TOKEN] = `Bearer ${token}`;
          }

          const response = await fetch(this.agentEndpointConfig.chatUrl, {
            body: JSON.stringify(request),
            headers,
            method: 'POST',
            signal: abortController.signal
          });

          if (!response.ok) {
            throw new Error(
              `Agent request failed with status ${response.status}.`
            );
          }

          if (!response.body) {
            throw new Error(
              'Agent response stream was unavailable for this request.'
            );
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let parserState = createAgentSseParserState();

          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              break;
            }

            const decodedChunk = decoder.decode(value, { stream: true });
            const parsedChunk = parseAgentSseChunk(decodedChunk, parserState);
            parserState = parsedChunk.state;

            for (const event of parsedChunk.events) {
              subscriber.next(event);
            }
          }

          const trailingChunk = decoder.decode();
          if (trailingChunk) {
            const parsedChunk = parseAgentSseChunk(trailingChunk, parserState);
            parserState = parsedChunk.state;

            for (const event of parsedChunk.events) {
              subscriber.next(event);
            }
          }

          const flushResult = flushAgentSseParserState(parserState);
          for (const event of flushResult.events) {
            subscriber.next(event);
          }

          subscriber.complete();
        } catch (error) {
          if (abortController.signal.aborted) {
            subscriber.complete();
            return;
          }

          subscriber.error(this.toError(error));
        }
      };

      void run();

      return () => {
        abortController.abort();
      };
    });
  }

  private toError(error: unknown): Error {
    if (error instanceof Error) {
      return error;
    }

    return new Error(DEFAULT_ERROR_MESSAGE);
  }
}
