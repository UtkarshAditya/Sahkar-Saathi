import { Component, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { RouterProvider } from 'react-router';
import { Button } from '@/components/common/Button';
import { AppProviders } from './providers';
import { router } from './router';

class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    return this.state.hasError ? <AppErrorFallback /> : this.props.children;
  }
}

function AppErrorFallback() {
  const { t } = useTranslation();
  return (
    <main
      role="alert"
      className="flex min-h-dvh flex-col items-center justify-center gap-3 px-4 text-center"
    >
      <h1 className="text-2xl font-bold">{t('app.crashTitle')}</h1>
      <p className="text-ink-soft">{t('app.crashBody')}</p>
      <Button size="lg" onClick={() => window.location.reload()}>
        {t('app.reload')}
      </Button>
    </main>
  );
}

export default function App() {
  return (
    <AppProviders>
      <AppErrorBoundary>
        <RouterProvider router={router} />
      </AppErrorBoundary>
    </AppProviders>
  );
}
