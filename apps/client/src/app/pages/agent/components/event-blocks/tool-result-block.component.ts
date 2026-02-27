import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-tool-result-block',
  styles: [
    `
      .tool-result-block {
        border: 2px solid #000;
        border-radius: 0.5rem;
        box-shadow: 3px 3px 0 #000;
        font-size: 0.85rem;
        font-weight: 500;
        padding: 0.5rem 0.75rem;
      }

      .tool-result-block.is-success {
        background: #bbf7d0;
        color: #166534;
      }

      .tool-result-block.is-error {
        background: #fecaca;
        color: #991b1b;
      }

      :host-context(.theme-dark) .tool-result-block {
        border-color: #e2e8f0;
        box-shadow: 3px 3px 0 rgba(255, 255, 255, 0.1);
      }

      :host-context(.theme-dark) .tool-result-block.is-success {
        background: #14532d;
        color: #4ade80;
      }

      :host-context(.theme-dark) .tool-result-block.is-error {
        background: #7f1d1d;
        color: #f87171;
      }
    `
  ],
  template: `
    <div
      class="tool-result-block"
      [class.is-error]="!success"
      [class.is-success]="success"
    >
      <div><strong>Tool:</strong> {{ tool }}</div>
      <div><strong>Status:</strong> {{ success ? 'Success' : 'Failed' }}</div>
      @if (!success && error) {
        <div><strong>Error:</strong> {{ error }}</div>
      }
    </div>
  `
})
export class GfToolResultBlockComponent {
  @Input() public error?: string;
  @Input() public success = false;
  @Input() public tool = 'unknown_tool';
}
