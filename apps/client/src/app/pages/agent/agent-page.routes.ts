import { AuthGuard } from '@ghostfolio/client/core/auth.guard';

import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./agent-page.component').then((c) => c.GfAgentPageComponent),
    path: '',
    title: 'Agent'
  }
];
