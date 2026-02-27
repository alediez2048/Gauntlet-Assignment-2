import { InjectionToken } from '@angular/core';

export interface AgentEndpointConfig {
  readonly chatUrl: string;
  readonly evalUrl: string;
}

// In production the NestJS backend proxies /api/v1/agent/* to the Python
// agent service, keeping the request same-origin (no CORS).  In local dev
// we fall through to the same proxy on http://localhost:3333.
const AGENT_CHAT_URL = '/api/v1/agent/chat';
const AGENT_EVAL_URL = '/api/v1/agent/eval';

export const AGENT_ENDPOINT_CONFIG = new InjectionToken<AgentEndpointConfig>(
  'AGENT_ENDPOINT_CONFIG',
  {
    providedIn: 'root',
    factory: () => ({
      get chatUrl(): string {
        return AGENT_CHAT_URL;
      },
      get evalUrl(): string {
        return AGENT_EVAL_URL;
      }
    })
  }
);
