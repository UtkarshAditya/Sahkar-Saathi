import {
  ClipboardList,
  Database,
  ExternalLink,
  FileText,
  MessagesSquare,
  Scale,
  Settings,
  ThumbsDown,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Card } from '@/components/common/Card';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { USE_MOCKS } from '@/services/api';

const MODULES = [
  {
    icon: FileText,
    title: 'Documents',
    body: 'Add documents, record publisher, date and version, and retire outdated ones without deleting them.',
    model: 'Document',
    href: '/admin/knowledge/document/',
  },
  {
    icon: Database,
    title: 'Chunks',
    body: 'Inspect the passages created from each document, with page, section, state and language.',
    model: 'Chunk',
    href: '/admin/knowledge/chunk/',
  },
  {
    icon: ThumbsDown,
    title: 'Feedback review',
    body: 'Review thumbs-down ratings and their reasons to find wrong or unclear answers.',
    model: 'Feedback',
    href: '/admin/feedback/feedback/?rating__exact=down',
  },
  {
    icon: MessagesSquare,
    title: 'Conversations',
    body: 'View anonymous conversations with answer status, top score, model and latency.',
    model: 'Conversation, Message, Citation',
    href: '/admin/chat/message/',
  },
  {
    icon: Scale,
    title: 'Grievance drafts',
    body: 'See which grievance categories are requested. Drafts are never filed.',
    model: 'GrievanceCase',
    href: null,
  },
  {
    icon: ClipboardList,
    title: 'Evaluation questions',
    body: 'Manage the 80-question test set and browse evaluation runs and results.',
    model: 'TestQuestion, EvalRun, EvalResult',
    href: null,
  },
];

/**
 * Overview of the Django admin site. With the real backend, Caddy (and the Vite dev proxy)
 * route /admin/ to Django, so the cards are plain links that leave the React app. In mock
 * mode there is no backend, so they are shown as not connected.
 */
export default function AdminPage() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader
        title={t('pages.admin.title')}
        description={t('pages.admin.description')}
        icon={<Settings className="size-6" aria-hidden />}
        badges={USE_MOCKS ? <Badge tone="neutral">Placeholder</Badge> : undefined}
      />

      <Notice tone="info" title="Provided by the backend" className="mb-6">
        Administration uses the built-in Django admin site at <code>/admin/</code>. Log in with a
        staff account; the team superuser is created on first start.
        {USE_MOCKS && ' Mock mode is on, so there is no backend to link to.'}
      </Notice>

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {MODULES.map((module) => (
          <li key={module.title}>
            <Card as="article" className="flex h-full flex-col">
              <span className="mb-3 flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <module.icon className="size-5" aria-hidden />
              </span>
              <h2 className="text-lg font-semibold">{module.title}</h2>
              <p className="mt-1 flex-1 text-ink-soft">{module.body}</p>
              <p className="mt-3 text-xs text-ink-muted">
                Django models: <span className="font-mono">{module.model}</span>
              </p>
              {module.href && !USE_MOCKS ? (
                <a
                  href={module.href}
                  className="mt-4 inline-flex min-h-10 items-center justify-center gap-1.5 self-start rounded-lg border border-line px-3 text-sm font-semibold text-brand-800 hover:bg-brand-50"
                >
                  Open in Django admin
                  <ExternalLink className="size-4" aria-hidden />
                </a>
              ) : (
                <span
                  aria-disabled="true"
                  className="mt-4 inline-flex min-h-10 cursor-not-allowed items-center justify-center self-start rounded-lg border border-dashed border-line px-3 text-sm font-semibold text-ink-muted"
                >
                  {module.href ? 'Not connected (mock mode)' : 'Coming in Sprint 2'}
                </span>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
