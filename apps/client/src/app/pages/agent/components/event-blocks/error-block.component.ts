import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-error-block',
  styles: [
    `
      .error-block {
        background: rgba(225, 46, 44, 0.1);
        border-left: 0.2rem solid rgba(225, 46, 44, 0.8);
        border-radius: 0.5rem;
        color: #842029;
        font-size: 0.9rem;
        padding: 0.65rem 0.75rem;
      }
    `
  ],
  template: `
    <div class="error-block">
      <strong>Error{{ code ? ' (' + code + ')' : '' }}:</strong> {{ message }}
    </div>
  `
})
export class GfErrorBlockComponent {
  @Input() public code = '';
  @Input() public message = 'Received an error from the portfolio service.';
}
