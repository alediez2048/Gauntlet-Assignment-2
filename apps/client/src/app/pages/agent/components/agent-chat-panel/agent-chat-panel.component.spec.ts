import { ComponentFixture, TestBed } from '@angular/core/testing';

import { of, Subject } from 'rxjs';

import { AgentStreamEvent } from '../../models/agent-chat.models';
import { AgentService } from '../../services/agent.service';
import { GfAgentChatPanelComponent } from './agent-chat-panel.component';

const globalWithLocalize = globalThis as typeof globalThis & {
  $localize?: (
    messageParts: TemplateStringsArray,
    ...expressions: readonly unknown[]
  ) => string;
};

describe('GfAgentChatPanelComponent', () => {
  let component: GfAgentChatPanelComponent;
  let fixture: ComponentFixture<GfAgentChatPanelComponent>;
  let mockAgentService: { streamChat: jest.Mock };

  beforeAll(() => {
    globalWithLocalize.$localize ??= (
      messageParts: TemplateStringsArray,
      ...expressions: readonly unknown[]
    ) => String.raw({ raw: messageParts }, ...expressions);
  });

  beforeEach(async () => {
    mockAgentService = {
      streamChat: jest.fn()
    };

    await TestBed.configureTestingModule({
      imports: [GfAgentChatPanelComponent],
      providers: [{ provide: AgentService, useValue: mockAgentService }]
    }).compileComponents();

    fixture = TestBed.createComponent(GfAgentChatPanelComponent);
    component = fixture.componentInstance;
    component.isOpen = true;
    fixture.detectChanges();
  });

  it('sends a prompt and renders streamed response blocks', () => {
    mockAgentService.streamChat.mockReturnValue(
      of<AgentStreamEvent>(
        {
          data: { message: 'Analyzing your request...' },
          event: 'thinking'
        },
        {
          data: { content: 'Portfolio net performance is 8.12%.' },
          event: 'token'
        },
        {
          data: {
            response: { message: 'Portfolio net performance is 8.12%.' },
            thread_id: 'thread-1'
          },
          event: 'done'
        }
      )
    );

    const textarea: HTMLTextAreaElement = fixture.nativeElement.querySelector(
      '[data-testid="agent-chat-input"]'
    );
    const sendButton: HTMLButtonElement = fixture.nativeElement.querySelector(
      '[data-testid="agent-send-button"]'
    );

    textarea.value = 'How is my portfolio doing ytd?';
    textarea.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    sendButton.click();
    fixture.detectChanges();

    expect(mockAgentService.streamChat).toHaveBeenCalledWith({
      message: 'How is my portfolio doing ytd?'
    });
    expect(component.chatState().threadId).toBe('thread-1');
    expect(component.chatState().isStreaming).toBe(false);
    expect(component.chatState().blocks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          content: 'How is my portfolio doing ytd?',
          type: 'user'
        }),
        expect.objectContaining({
          content: 'Portfolio net performance is 8.12%.',
          type: 'assistant'
        })
      ])
    );
  });

  it('reuses thread_id on subsequent sends', () => {
    mockAgentService.streamChat
      .mockReturnValueOnce(
        of<AgentStreamEvent>({
          data: {
            response: { message: 'Initial response' },
            thread_id: 'thread-abc'
          },
          event: 'done'
        })
      )
      .mockReturnValueOnce(
        of<AgentStreamEvent>({
          data: {
            response: { message: 'Follow-up response' },
            thread_id: 'thread-abc'
          },
          event: 'done'
        })
      );

    component.draftMessage = 'First question';
    component.onSendMessage();
    fixture.detectChanges();

    component.draftMessage = 'Second question';
    component.onSendMessage();
    fixture.detectChanges();

    expect(mockAgentService.streamChat).toHaveBeenNthCalledWith(1, {
      message: 'First question'
    });
    expect(mockAgentService.streamChat).toHaveBeenNthCalledWith(2, {
      message: 'Second question',
      thread_id: 'thread-abc'
    });
  });

  it('disables send while stream is active', () => {
    const streamSubject = new Subject<AgentStreamEvent>();
    mockAgentService.streamChat.mockReturnValue(streamSubject.asObservable());

    component.draftMessage = 'Tell me about allocations';
    component.onSendMessage();
    fixture.detectChanges();

    const sendButton: HTMLButtonElement = fixture.nativeElement.querySelector(
      '[data-testid="agent-send-button"]'
    );

    expect(component.chatState().isStreaming).toBe(true);
    expect(sendButton.disabled).toBe(true);

    streamSubject.next({
      data: {
        response: { message: 'Done' },
        thread_id: 'thread-xyz'
      },
      event: 'done'
    });
    streamSubject.complete();
    fixture.detectChanges();

    expect(component.chatState().isStreaming).toBe(false);
  });
});
