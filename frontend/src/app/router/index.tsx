import { createBrowserRouter, Navigate, redirect, type LoaderFunctionArgs } from 'react-router';
import { AppShell } from '../../components/AppShell';
import { LoginScreen, ProtectedRoute } from '../../features/auth';
import { ComposerScreen } from '../../features/composer';
import { AccountsScreen } from '../../features/accounts';
import { FilesScreen } from '../../features/media';
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
      { path: 'overview', element: <Navigate to="/compose" replace /> },
      { path: 'compose', element: <ComposerScreen /> },
      { path: 'compose/:draftId', element: <ComposerScreen /> },
      { path: 'library', element: <FilesScreen /> },
      { path: 'publications', element: <PublicationsScreen /> },
      { path: 'publications/:id', element: <PublicationScreen /> },
      { path: 'platforms', element: <AccountsScreen /> },
      { path: 'account', element: <Navigate to="/platforms" replace /> },
      { path: 'files', element: <Navigate to="/library" replace /> },
      { path: 'settings/accounts', loader: redirectWithQuery('/platforms') },
    ],
  },
  { path: '*', element: <Navigate to="/compose" replace /> },
]);
