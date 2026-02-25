import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { GfAgentFabComponent } from './agent-fab.component';

const globalWithLocalize = globalThis as typeof globalThis & {
  $localize?: (
    messageParts: TemplateStringsArray,
    ...expressions: readonly unknown[]
  ) => string;
};

describe('GfAgentFabComponent', () => {
  let component: GfAgentFabComponent;
  let fixture: ComponentFixture<GfAgentFabComponent>;

  beforeAll(() => {
    globalWithLocalize.$localize ??= (
      messageParts: TemplateStringsArray,
      ...expressions: readonly unknown[]
    ) => String.raw({ raw: messageParts }, ...expressions);
  });

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GfAgentFabComponent]
    }).compileComponents();

    fixture = TestBed.createComponent(GfAgentFabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('opens panel from FAB and hides FAB while open', () => {
    const button: HTMLButtonElement | null = fixture.nativeElement.querySelector(
      '.agent-fab-button'
    );

    expect(component.isPanelOpen()).toBe(false);
    expect(button).not.toBeNull();

    button?.click();
    fixture.detectChanges();

    expect(component.isPanelOpen()).toBe(true);
    expect(fixture.nativeElement.querySelector('.agent-fab-button')).toBeNull();

    const panel = fixture.debugElement.query(By.css('gf-agent-chat-panel'));
    panel.triggerEventHandler('closeRequested', undefined);
    fixture.detectChanges();

    expect(component.isPanelOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('.agent-fab-button')).not.toBeNull();
  });

  it('closes panel when chat panel emits closeRequested', () => {
    component.isPanelOpen.set(true);
    fixture.detectChanges();

    const panel = fixture.debugElement.query(By.css('gf-agent-chat-panel'));
    panel.triggerEventHandler('closeRequested', undefined);
    fixture.detectChanges();

    expect(component.isPanelOpen()).toBe(false);
  });
});
