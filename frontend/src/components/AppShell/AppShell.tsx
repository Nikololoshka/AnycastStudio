import { Outlet } from 'react-router';
import { AppSidebar } from './AppSidebar';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col bg-window-backdrop text-foreground min-[900px]:flex-row">
      <AppSidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-x-clip">
        <AppTopBar />
        <div className="flex flex-1 flex-col px-4 pt-2 pb-12 sm:px-6 lg:px-10">
          <div className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
