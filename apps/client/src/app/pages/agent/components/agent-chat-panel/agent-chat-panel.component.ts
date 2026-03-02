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
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { Subscription } from 'rxjs';

import {
  AgentChatRequest,
  AgentChatState,
  EvalCaseResult,
  EvalRunState,
  EvalStreamEvent,
  EvalSummary,
  INITIAL_AGENT_CHAT_STATE,
  INITIAL_EVAL_RUN_STATE
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

interface QuestionCategory {
  label: string;
  questions: string[];
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSlideToggleModule,
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
  public expandedCategory: string | null = null;
  public isTestingMode = false;
  public readonly userCategories: QuestionCategory[] = [
    {
      label: 'Portfolio',
      questions: [
        'How is my portfolio performing?',
        'What are my holdings worth?',
        'Am I well diversified?'
      ]
    },
    {
      label: 'Taxes',
      questions: [
        'Estimate my capital gains tax this year.',
        'What are my tax-loss harvesting opportunities?',
        'How tax-efficient is my portfolio?'
      ]
    },
    {
      label: 'Compliance',
      questions: [
        'Check my portfolio for compliance issues.',
        'Do I have any concentration risk?',
        'Are there any regulatory flags in my holdings?'
      ]
    },
    {
      label: 'Prediction Markets',
      questions: [
        'What prediction markets are trending?',
        'Show my Polymarket positions.',
        'Analyze the top prediction markets by volume.'
      ]
    }
  ];
  public readonly chatState = signal<AgentChatState>(INITIAL_AGENT_CHAT_STATE);
  public readonly evalState = signal<EvalRunState>(INITIAL_EVAL_RUN_STATE);
  public readonly questionCategories: QuestionCategory[] = [
    {
      label: 'Single Tool',
      questions: [
        'How is my portfolio performing?',
        'Categorize my recent transactions.',
        'Estimate my taxes for this year.',
        'Check my portfolio for compliance issues.',
        'What are the current prices of my holdings?'
      ]
    },
    {
      label: 'Multi-Tool',
      questions: [
        'Give me a full financial health checkup.',
        'Am I diversified enough and tax-efficient?',
        'Analyze my portfolio and check for compliance issues.'
      ]
    },
    {
      label: 'Edge Cases',
      questions: [
        'What is the weather like today?',
        'Write me a Python script.',
        'Tell me a joke about stocks.'
      ]
    }
  ];
  private evalSubscription?: Subscription;
  private streamSubscription?: Subscription;

  public constructor(private agentService: AgentService) {}

  public get canSendMessage() {
    return !this.chatState().isStreaming && !!this.draftMessage.trim();
  }

  public ngOnDestroy() {
    this.cancelActiveStream(false);
    this.onCancelEvals();
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

  public onToggleTestingMode() {
    this.isTestingMode = !this.isTestingMode;
    this.expandedCategory = null;
  }

  public onToggleCategory(label: string) {
    this.expandedCategory = this.expandedCategory === label ? null : label;
  }

  public onSampleQuestionClick(question: string) {
    this.draftMessage = question;
    this.onSendMessage();
  }

  public onRunEvals() {
    if (this.evalState().isRunning) {
      return;
    }

    this.onCancelEvals();
    this.evalState.set({ ...INITIAL_EVAL_RUN_STATE, isRunning: true });

    this.evalSubscription = this.agentService.streamEval().subscribe({
      complete: () => {
        this.evalState.update((state) => ({ ...state, isRunning: false }));
      },
      error: (error: unknown) => {
        this.evalState.update((state) => ({
          ...state,
          isRunning: false,
          error:
            error instanceof Error
              ? error.message
              : 'Eval run failed unexpectedly.'
        }));
      },
      next: (event) => {
        this.evalState.update((state) => this.reduceEvalEvent(state, event));
      }
    });

    this.evalSubscription.add(() => {
      this.evalSubscription = undefined;
    });
  }

  public onCancelEvals() {
    if (this.evalSubscription) {
      this.evalSubscription.unsubscribe();
      this.evalState.update((state) => ({ ...state, isRunning: false }));
    }
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

  private reduceEvalEvent(
    state: EvalRunState,
    event: EvalStreamEvent
  ): EvalRunState {
    switch (event.event) {
      case 'eval_start':
        return {
          ...state,
          totalCases: (event.data['total_cases'] as number) ?? 0
        };
      case 'eval_result': {
        const result = event.data as unknown as EvalCaseResult;
        return {
          ...state,
          completedCases: state.completedCases + 1,
          results: [...state.results, result]
        };
      }
      case 'eval_done': {
        const summary = event.data as unknown as EvalSummary;
        return {
          ...state,
          isRunning: false,
          summary,
          error: (event.data['error'] as string) ?? null
        };
      }
      default:
        return state;
    }
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
