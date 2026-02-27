import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatProgressSpinnerModule],
  selector: 'gf-agent-thinking-block',
  styles: [
    `
      .thinking-block {
        align-items: center;
        background: #fef9c3;
        border: 2px solid #000;
        border-radius: 0.5rem;
        box-shadow: 3px 3px 0 #000;
        color: #854d0e;
        display: flex;
        font-size: 0.9rem;
        font-weight: 600;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
      }

      :host-context(.theme-dark) .thinking-block {
        background: #374151;
        border-color: #e2e8f0;
        box-shadow: 3px 3px 0 rgba(255, 255, 255, 0.1);
        color: #fbbf24;
      }
    `
  ],
  template: `
    <div class="thinking-block">
      <mat-spinner [diameter]="14" />
      <span>{{ message }}</span>
    </div>
  `
})
export class GfThinkingBlockComponent {
  @Input() public message = 'Analyzing your request...';
}
