import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
  ViewChild,
  signal
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Subscription } from 'rxjs';

import {
  AgentChatRequest,
  AgentChatState,
  AgentFeedbackRequest,
  INITIAL_AGENT_CHAT_STATE
} from '../../models/agent-chat.models';
import {
  AgentChatAction,
  reduceAgentChatState
} from '../../services/agent-chat.reducer';
import { AgentService } from '../../services/agent.service';
import { GfErrorBlockComponent } from '../event-blocks/error-block.component';
import { GfThinkingBlockComponent } from '../event-blocks/thinking-block.component';
import { GfToolCallBlockComponent } from '../event-blocks/tool-call-block.component';
import { GfToolResultBlockComponent } from '../event-blocks/tool-result-block.component';

const STREAM_INCOMPLETE_MESSAGE =
  'The stream ended before a final response was received.';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    GfErrorBlockComponent,
    GfThinkingBlockComponent,
    GfToolCallBlockComponent,
    GfToolResultBlockComponent
  ],
  selector: 'gf-agent-chat-panel',
  styleUrls: ['./agent-chat-panel.component.scss'],
  templateUrl: './agent-chat-panel.component.html'
})
export class GfAgentChatPanelComponent implements OnDestroy {
  @Input() public isOpen = false;
  @Output() public closeRequested = new EventEmitter<void>();
  @ViewChild('messageContainer')
  private messageContainer?: ElementRef<HTMLElement>;

  public draftMessage = '';
  public readonly chatState = signal<AgentChatState>(INITIAL_AGENT_CHAT_STATE);
  public readonly sampleQuestions = [
    'How is my portfolio performing?',
    'Estimate my taxes for this year.',
    'Am I properly diversified?',
    'Check my portfolio for compliance issues.',
    'Categorize my recent transactions.'
  ];
  private streamSubscription?: Subscription;

  public constructor(private agentService: AgentService) {}

  public get canSendMessage() {
    return !this.chatState().isStreaming && !!this.draftMessage.trim();
  }

  public ngOnDestroy() {
    this.cancelActiveStream(false);
  }

  public onCancelStream() {
    this.cancelActiveStream(true);
  }

  public onDraftMessageInput(event: Event) {
    const inputElement = event.target as HTMLTextAreaElement | null;
    this.draftMessage = inputElement?.value ?? '';
  }

  public onInputKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.onSendMessage();
    }
  }

  public onRequestClose() {
    this.cancelActiveStream(true);
    this.closeRequested.emit();
  }

  public onFeedback(blockIndex: number, rating: 'up' | 'down') {
    const threadId = this.chatState().threadId;
    if (!threadId) {
      return;
    }

    this.applyAction({ blockIndex, rating, type: 'set_feedback' });

    const request: AgentFeedbackRequest = {
      message_index: blockIndex,
      rating,
      thread_id: threadId
    };

    this.agentService.submitFeedback(request).catch(() => {
      // Feedback is best-effort; do not disrupt the UI on failure.
    });
  }

  public onSampleQuestionClick(question: string) {
    this.draftMessage = question;
    this.onSendMessage();
  }

  public onSendMessage() {
    const message = this.draftMessage.trim();
    if (!message || this.chatState().isStreaming) {
      return;
    }

    this.cancelActiveStream(false);

    const request: AgentChatRequest = {
      message
    };

    const activeThreadId = this.chatState().threadId;
    if (activeThreadId) {
      request.thread_id = activeThreadId;
    }

    this.applyAction({ message, type: 'start_turn' });
    this.draftMessage = '';

    const subscription = this.agentService.streamChat(request).subscribe({
      complete: () => {
        if (this.chatState().isStreaming) {
          this.applyAction({
            message: STREAM_INCOMPLETE_MESSAGE,
            type: 'stream_error'
          });
        }
      },
      error: (error: unknown) => {
        this.applyAction({
          message: this.resolveErrorMessage(error),
          type: 'stream_error'
        });
      },
      next: (event) => {
        this.applyAction({ event, type: 'stream_event' });
      }
    });

    subscription.add(() => {
      this.streamSubscription = undefined;
    });

    this.streamSubscription = subscription;
  }

  private applyAction(action: AgentChatAction) {
    this.chatState.update((state) => reduceAgentChatState(state, action));
    this.scheduleScrollToBottom();
  }

  private cancelActiveStream(updateState: boolean) {
    if (!this.streamSubscription) {
      return;
    }

    this.streamSubscription.unsubscribe();

    if (updateState && this.chatState().isStreaming) {
      this.applyAction({ type: 'cancel_turn' });
    }
  }

  private resolveErrorMessage(error: unknown) {
    if (error instanceof Error && error.message) {
      return error.message;
    }

    return 'Unable to reach the agent service. Verify it is running and try again.';
  }

  private scheduleScrollToBottom() {
    queueMicrotask(() => {
      const containerElement = this.messageContainer?.nativeElement;
      if (!containerElement) {
        return;
      }

      containerElement.scrollTop = containerElement.scrollHeight;
    });
  }
}
