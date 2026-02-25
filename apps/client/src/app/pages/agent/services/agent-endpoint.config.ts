import { InjectionToken } from '@angular/core';

export interface AgentEndpointConfig {
  chatUrl: string;
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

export const AGENT_ENDPOINT_CONFIG = new InjectionToken<AgentEndpointConfig>(
  'AGENT_ENDPOINT_CONFIG',
  {
    providedIn: 'root',
    factory: () => ({
      chatUrl: resolveAgentChatUrl()
    })
  }
);
