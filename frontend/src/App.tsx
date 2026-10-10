import React, { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { router } from './router';
import { bootstrapDevToken, isTokenValid } from './api/auth';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  useEffect(() => {
    // Bootstrap a dev JWT on first load (or if expired).
    // In production this would redirect to OIDC.
    if (!isTokenValid()) {
      bootstrapDevToken({
        subject: 'dev-national-admin',
        roles: ['national_admin'],
      }).catch(console.error);
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
