import React from 'react';
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ComponentGallery } from '@/design/gallery/ComponentGallery';

// Lazy-loaded pages
const Overview = React.lazy(() => import('@/pages/Overview').then(m => ({ default: m.OverviewPage })));
const Centres = React.lazy(() => import('@/pages/Centres').then(m => ({ default: m.CentresPage })));
const CentreDetail = React.lazy(() => import('@/pages/CentreDetail').then(m => ({ default: m.CentreDetailPage })));
const FlagsCases = React.lazy(() => import('@/pages/FlagsCases').then(m => ({ default: m.FlagsCasesPage })));
const CameraIntegrity = React.lazy(() => import('@/pages/CameraIntegrity').then(m => ({ default: m.CameraIntegrityPage })));
const GhostBatches = React.lazy(() => import('@/pages/GhostBatches').then(m => ({ default: m.GhostBatchesPage })));
const EdgeConsole = React.lazy(() => import('@/pages/EdgeConsole').then(m => ({ default: m.EdgeConsolePage })));
const Settings = React.lazy(() => import('@/pages/Settings').then(m => ({ default: m.SettingsPage })));
const AuditLog = React.lazy(() => import('@/pages/AuditLog').then(m => ({ default: m.AuditLogPage })));
const AccuracyLimits = React.lazy(() => import('@/pages/AccuracyLimits').then(m => ({ default: m.AccuracyLimitsPage })));

function Suspense({ children }: { children: React.ReactNode }) {
  return (
    <React.Suspense
      fallback={
        <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
          Loading…
        </div>
      }
    >
      {children}
    </React.Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: '/gallery',
    element: <ComponentGallery />,
  },
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Suspense><Overview /></Suspense> },
      { path: 'centres', element: <Suspense><Centres /></Suspense> },
      { path: 'centres/:id', element: <Suspense><CentreDetail /></Suspense> },
      { path: 'flags', element: <Suspense><FlagsCases /></Suspense> },
      { path: 'camera-integrity', element: <Suspense><CameraIntegrity /></Suspense> },
      { path: 'camera-integrity/:cameraId', element: <Suspense><CameraIntegrity /></Suspense> },
      { path: 'ghost-batches', element: <Suspense><GhostBatches /></Suspense> },
      { path: 'ghost-batches/:batchId', element: <Suspense><GhostBatches /></Suspense> },
      { path: 'edge-console', element: <Suspense><EdgeConsole /></Suspense> },
      { path: 'settings', element: <Suspense><Settings /></Suspense> },
      { path: 'audit-log', element: <Suspense><AuditLog /></Suspense> },
      { path: 'accuracy', element: <Suspense><AccuracyLimits /></Suspense> },
    ],
  },
]);
