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
        background: var(--light-background-secondary);
        border-radius: 0.5rem;
        color: var(--dark-font-secondary-color);
        display: flex;
        font-size: 0.9rem;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
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
