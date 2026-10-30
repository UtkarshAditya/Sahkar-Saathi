import { createBrowserRouter } from 'react-router';
import AppLayout from '@/components/layout/AppLayout';
import AboutPage from '@/pages/AboutPage';
import AdminPage from '@/pages/AdminPage';
import AskPage from '@/pages/AskPage';
import FinancialLiteracyPage from '@/pages/FinancialLiteracyPage';
import GrievancePage from '@/pages/GrievancePage';
import LawLibraryPage from '@/pages/LawLibraryPage';
import NotFoundPage from '@/pages/NotFoundPage';
import QualityDashboardPage from '@/pages/QualityDashboardPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <AskPage /> },
      { path: 'grievance', element: <GrievancePage /> },
      { path: 'about', element: <AboutPage /> },
      { path: 'library', element: <LawLibraryPage /> },
      { path: 'learn', element: <FinancialLiteracyPage /> },
      { path: 'staff/quality', element: <QualityDashboardPage /> },
      { path: 'admin', element: <AdminPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
