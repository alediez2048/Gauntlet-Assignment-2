import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'gf-agent-error-block',
  styles: [
    `
      .error-block {
        background: #fecaca;
        border: 2px solid #991b1b;
        border-radius: 0.5rem;
        box-shadow: 3px 3px 0 #991b1b;
        color: #991b1b;
        font-size: 0.9rem;
        font-weight: 600;
        padding: 0.65rem 0.75rem;
      }

      :host-context(.theme-dark) .error-block {
        background: #7f1d1d;
        border-color: #f87171;
        box-shadow: 3px 3px 0 rgba(248, 113, 113, 0.3);
        color: #f87171;
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
