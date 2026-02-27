import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-tool-call-block',
  styles: [
    `
      .tool-call-block {
        background: #dbeafe;
        border: 2px solid #000;
        border-radius: 0.5rem;
        box-shadow: 3px 3px 0 #000;
        font-size: 0.85rem;
        font-weight: 500;
        padding: 0.5rem 0.75rem;
      }

      .tool-call-block code {
        white-space: pre-wrap;
      }

      :host-context(.theme-dark) .tool-call-block {
        background: #1e3a5f;
        border-color: #e2e8f0;
        box-shadow: 3px 3px 0 rgba(255, 255, 255, 0.1);
        color: #e2e8f0;
      }
    `
  ],
  template: `
    <div class="tool-call-block">
      <div><strong>Tool:</strong> {{ tool }}</div>
      <div>
        <strong>Args:</strong> <code>{{ argsSummary }}</code>
      </div>
    </div>
  `
})
export class GfToolCallBlockComponent {
  @Input() public args: Record<string, unknown> = {};
  @Input() public tool = 'unknown_tool';

  public get argsSummary() {
    return JSON.stringify(this.args);
  }
}
