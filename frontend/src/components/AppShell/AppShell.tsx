import { Outlet } from 'react-router';
import { PublicationsSidebar } from '../../features/publications';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-window-backdrop text-foreground">
      <AppTopBar />
      <div className="flex min-h-0 flex-1">
        <PublicationsSidebar />
        <main className="min-w-0 flex-1 overflow-y-auto px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
