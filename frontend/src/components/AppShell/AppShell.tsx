import { Outlet } from 'react-router';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <div className="flex min-h-screen w-full flex-col bg-window-backdrop text-foreground">
      <AppTopBar />
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 pb-8">
        <Outlet />
      </div>
    </div>
  );
}
