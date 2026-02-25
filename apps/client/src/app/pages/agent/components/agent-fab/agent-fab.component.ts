import {
  ChangeDetectionStrategy,
  Component,
  signal
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { GfAgentChatPanelComponent } from '../agent-chat-panel/agent-chat-panel.component';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatIconModule, GfAgentChatPanelComponent],
  selector: 'gf-agent-fab',
  styleUrls: ['./agent-fab.component.scss'],
  templateUrl: './agent-fab.component.html'
})
export class GfAgentFabComponent {
  public readonly isPanelOpen = signal(false);

  public onOpenPanel() {
    this.isPanelOpen.set(true);
  }

  public onClosePanel() {
    this.isPanelOpen.set(false);
  }
}
