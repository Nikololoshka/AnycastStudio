import { Outlet } from 'react-router';
import { AppSidebar } from './AppSidebar';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col bg-window-backdrop text-foreground min-[900px]:flex-row">
      <AppSidebar />
      <main className="min-w-0 flex-1">
        <AppTopBar />
        <div className="px-4 pt-2 pb-12 sm:px-6 lg:px-10">
          <div className="mx-auto max-w-[1200px]">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
