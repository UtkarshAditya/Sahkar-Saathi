import { createBrowserRouter } from 'react-router';
import AppLayout from '@/components/layout/AppLayout';
import AboutPage from '@/pages/AboutPage';
import AdminPage from '@/pages/AdminPage';
import AskPage from '@/pages/AskPage';
import CropInsurancePage from '@/pages/CropInsurancePage';
import FinancialLiteracyPage from '@/pages/FinancialLiteracyPage';
import GrievancePage from '@/pages/GrievancePage';
import LawLibraryPage from '@/pages/LawLibraryPage';
import NotFoundPage from '@/pages/NotFoundPage';
import QualityDashboardPage from '@/pages/QualityDashboardPage';
import SchemesPage from '@/pages/SchemesPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <AskPage /> },
      { path: 'grievance', element: <GrievancePage /> },
      { path: 'about', element: <AboutPage /> },
      { path: 'crop-insurance', element: <CropInsurancePage /> },
      { path: 'schemes', element: <SchemesPage /> },
      { path: 'library', element: <LawLibraryPage /> },
      { path: 'learn', element: <FinancialLiteracyPage /> },
      { path: 'staff/quality', element: <QualityDashboardPage /> },
      { path: 'admin', element: <AdminPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
