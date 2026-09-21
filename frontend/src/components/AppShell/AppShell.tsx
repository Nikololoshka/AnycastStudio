import type { ReactNode } from 'react';
import { AppTopBar } from './AppTopBar';
import { useWindowMaximized } from './useWindowMaximized';

export function AppShell({
  left,
  center,
  right,
}: {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}) {
  const isMaximized = useWindowMaximized();

  return (
    <div
      className={`flex h-screen w-full flex-col overflow-hidden bg-window-backdrop text-foreground ${
        isMaximized ? '' : 'rounded-xl border border-border'
      }`}
    >
      <AppTopBar />
      <div className="grid min-h-0 flex-1 grid-cols-[248px_minmax(0,1fr)_340px] gap-3 px-3 pb-3">
        <aside className="min-h-0 overflow-y-auto rounded-2xl border border-border bg-surface shadow-[var(--panel-shadow)]">
          {left}
        </aside>
        <main className="min-h-0 overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--panel-shadow)]">
          {center}
        </main>
        <aside className="min-h-0 overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--panel-shadow)]">
          {right}
        </aside>
      </div>
    </div>
  );
}
