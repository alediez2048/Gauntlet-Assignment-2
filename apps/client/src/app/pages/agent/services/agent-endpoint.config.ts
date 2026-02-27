import { InjectionToken } from '@angular/core';

export interface AgentEndpointConfig {
  readonly chatUrl: string;
}

declare global {
  interface Window {
    __GF_AGENT_CHAT_URL__?: string;
  }
}

const DEFAULT_AGENT_CHAT_URL = 'http://localhost:8000/api/agent/chat';

const resolveAgentChatUrl = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_AGENT_CHAT_URL;
  }

  const runtimeChatUrl = window.__GF_AGENT_CHAT_URL__;

  if (typeof runtimeChatUrl === 'string' && runtimeChatUrl.trim()) {
    return runtimeChatUrl.trim();
  }

  return DEFAULT_AGENT_CHAT_URL;
};

let _cachedUrl: string | null = null;

export const AGENT_ENDPOINT_CONFIG = new InjectionToken<AgentEndpointConfig>(
  'AGENT_ENDPOINT_CONFIG',
  {
    providedIn: 'root',
    factory: () => ({
      get chatUrl(): string {
        if (_cachedUrl) {
          return _cachedUrl;
        }

        const url = resolveAgentChatUrl();
        if (url !== DEFAULT_AGENT_CHAT_URL) {
          _cachedUrl = url;
        }

        return url;
      }
    })
  }
);
