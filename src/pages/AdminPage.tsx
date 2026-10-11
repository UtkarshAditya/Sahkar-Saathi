import {
  ClipboardList,
  Database,
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

const MODULES = [
  {
    icon: FileText,
    title: 'Documents',
    body: 'Add documents, record publisher, date and version, and retire outdated ones without deleting them.',
    model: 'Document',
  },
  {
    icon: Database,
    title: 'Chunks',
    body: 'Inspect the passages created from each document, with page, section, state and language.',
    model: 'Chunk',
  },
  {
    icon: ThumbsDown,
    title: 'Feedback review',
    body: 'Review thumbs-down ratings and their reasons to find wrong or unclear answers.',
    model: 'Feedback',
  },
  {
    icon: MessagesSquare,
    title: 'Conversations',
    body: 'View anonymous conversations with answer status, top score, model and latency.',
    model: 'Conversation, Message, Citation',
  },
  {
    icon: Scale,
    title: 'Grievance drafts',
    body: 'See which grievance categories are requested. Drafts are never filed.',
    model: 'GrievanceCase',
  },
  {
    icon: ClipboardList,
    title: 'Evaluation questions',
    body: 'Manage the 80-question test set and browse evaluation runs and results.',
    model: 'TestQuestion, EvalRun, EvalResult',
  },
];

/**
 * Front-end placeholder only. In the deployed setup Caddy should route /admin to Django,
 * so this page is only reachable in the Vite dev server.
 */
export default function AdminPage() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader
        title={t('pages.admin.title')}
        description={t('pages.admin.description')}
        icon={<Settings className="size-6" aria-hidden />}
        breadcrumbs={[{ label: t('nav.groups.staff') }]}
        badges={<Badge tone="neutral">Placeholder</Badge>}
      />

      <Notice tone="info" title="Provided by the backend" className="mb-6">
        Administration will use the built-in Django admin site, served at <code>/admin/</code> by
        the backend. This React page only shows what will be available. There is no login or data
        here.
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
              <span
                aria-disabled="true"
                className="mt-4 inline-flex min-h-10 cursor-not-allowed items-center justify-center self-start rounded-lg border border-dashed border-line px-3 text-sm font-semibold text-ink-muted"
              >
                Opens in Django admin (not connected)
              </span>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
