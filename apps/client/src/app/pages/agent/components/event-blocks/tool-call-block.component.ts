import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-tool-call-block',
  styles: [
    `
      .tool-call-block {
        background: rgba(46, 91, 255, 0.08);
        border-left: 0.2rem solid rgba(46, 91, 255, 0.6);
        border-radius: 0.5rem;
        font-size: 0.85rem;
        padding: 0.5rem 0.75rem;
      }

      .tool-call-block code {
        white-space: pre-wrap;
      }
    `
  ],
  template: `
    <div class="tool-call-block">
      <div><strong>Tool:</strong> {{ tool }}</div>
      <div><strong>Args:</strong> <code>{{ argsSummary }}</code></div>
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
