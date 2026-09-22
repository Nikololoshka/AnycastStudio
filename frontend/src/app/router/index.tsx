import { createBrowserRouter, Navigate } from 'react-router';
import { AppShell } from '../../components/AppShell';
import { LoginScreen, ProtectedRoute } from '../../features/auth';
import { ComposerScreen } from '../../features/composer';
import { AccountsScreen } from '../../features/accounts';
import { PublicationScreen, PublicationsScreen } from '../../features/publications';

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
      { index: true, element: <Navigate to="/compose" replace /> },
      { path: 'compose', element: <ComposerScreen /> },
      { path: 'publications', element: <PublicationsScreen /> },
      { path: 'publications/:id', element: <PublicationScreen /> },
      { path: 'settings/accounts', element: <AccountsScreen /> },
    ],
  },
  { path: '*', element: <Navigate to="/compose" replace /> },
]);
