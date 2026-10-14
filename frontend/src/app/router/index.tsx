import { createBrowserRouter, Navigate, redirect, type LoaderFunctionArgs } from 'react-router';
import { AppShell } from '../../components/AppShell';
import { AccountScreen } from '../../features/account';
import { LoginScreen, ProtectedRoute } from '../../features/auth';
import { ComposerScreen } from '../../features/composer';
import { PlatformsScreen } from '../../features/accounts';
import { LibraryScreen } from '../../features/media';
import { OverviewScreen } from '../../features/overview';
import { PublicationScreen, PublicationsScreen } from '../../features/publications';

function redirectWithQuery(to: string) {
  return ({ request }: LoaderFunctionArgs) => redirect(to + new URL(request.url).search);
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginScreen /> },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      { path: 'overview', element: <OverviewScreen /> },
      { path: 'compose', element: <ComposerScreen /> },
      { path: 'compose/:draftId', element: <ComposerScreen /> },
      { path: 'library', element: <LibraryScreen /> },
      { path: 'publications', element: <PublicationsScreen /> },
      { path: 'publications/:id', element: <PublicationScreen /> },
      { path: 'platforms', element: <PlatformsScreen /> },
      { path: 'account', element: <AccountScreen /> },
      { path: 'files', element: <Navigate to="/library" replace /> },
      { path: 'settings/accounts', loader: redirectWithQuery('/platforms') },
    ],
  },
  { path: '*', element: <Navigate to="/overview" replace /> },
]);
