import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter } from 'react-router';
import { LoadingState } from '@/components/common/EmptyState';
import AppLayout from '@/components/layout/AppLayout';

const AboutPage = lazy(() => import('@/pages/AboutPage'));
const AdminPage = lazy(() => import('@/pages/AdminPage'));
const AskPage = lazy(() => import('@/pages/AskPage'));
const CropInsurancePage = lazy(() => import('@/pages/CropInsurancePage'));
const FinancialLiteracyPage = lazy(() => import('@/pages/FinancialLiteracyPage'));
const GrievancePage = lazy(() => import('@/pages/GrievancePage'));
const LawLibraryPage = lazy(() => import('@/pages/LawLibraryPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const QualityDashboardPage = lazy(() => import('@/pages/QualityDashboardPage'));
const SchemesPage = lazy(() => import('@/pages/SchemesPage'));

function routeContent(page: ReactNode) {
  return <Suspense fallback={<LoadingState />}>{page}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: routeContent(<AskPage />) },
      { path: 'grievance', element: routeContent(<GrievancePage />) },
      { path: 'about', element: routeContent(<AboutPage />) },
      { path: 'crop-insurance', element: routeContent(<CropInsurancePage />) },
      { path: 'schemes', element: routeContent(<SchemesPage />) },
      { path: 'library', element: routeContent(<LawLibraryPage />) },
      { path: 'learn', element: routeContent(<FinancialLiteracyPage />) },
      { path: 'staff/quality', element: routeContent(<QualityDashboardPage />) },
      { path: 'admin', element: routeContent(<AdminPage />) },
      { path: '*', element: routeContent(<NotFoundPage />) },
    ],
  },
]);
