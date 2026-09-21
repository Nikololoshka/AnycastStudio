import type { ReactNode } from 'react';
import { Spinner } from '@heroui/react';
import { Navigate } from 'react-router';
import { useGetSessionQuery } from '../../api';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useGetSessionQuery();

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-window-backdrop">
        <Spinner />
      </div>
    );
  }

  return user ? <>{children}</> : <Navigate to="/login" replace />;
}
