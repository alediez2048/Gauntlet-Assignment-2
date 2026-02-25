import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-tool-result-block',
  styles: [
    `
      .tool-result-block {
        border-radius: 0.5rem;
        font-size: 0.85rem;
        padding: 0.5rem 0.75rem;
      }

      .tool-result-block.is-success {
        background: rgba(42, 145, 52, 0.12);
        border-left: 0.2rem solid rgba(42, 145, 52, 0.7);
      }

      .tool-result-block.is-error {
        background: rgba(225, 46, 44, 0.12);
        border-left: 0.2rem solid rgba(225, 46, 44, 0.7);
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
