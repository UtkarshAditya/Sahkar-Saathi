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
import { Card } from '@/components/common/Card';
import { PageHeader } from '@/components/common/PageHeader';
import { USE_MOCKS } from '@/services/api';

const MODULES = [
  {
    icon: FileText,
    title: 'Documents',
    body: 'Add documents, record publisher, date and version, and retire outdated ones without deleting them.',
    href: '/admin/knowledge/document/',
  },
  {
    icon: Database,
    title: 'Chunks',
    body: 'Inspect the passages created from each document, with page, section, state and language.',
    href: '/admin/knowledge/chunk/',
  },
  {
    icon: ThumbsDown,
    title: 'Feedback review',
    body: 'Review thumbs-down ratings and their reasons to find wrong or unclear answers.',
    href: '/admin/feedback/feedback/?rating__exact=down',
  },
  {
    icon: MessagesSquare,
    title: 'Conversations',
    body: 'View anonymous conversations with answer status, top score, model and latency.',
    href: '/admin/chat/message/',
  },
  {
    icon: Scale,
    title: 'Grievance drafts',
    body: 'See which grievance categories are requested. Drafts are never filed.',
    href: null,
  },
  {
    icon: ClipboardList,
    title: 'Evaluation questions',
    body: 'Manage the 80-question test set and browse evaluation runs and results.',
    href: null,
  },
];

/** Overview of the Django admin site. */
export default function AdminPage() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader
        title={t('pages.admin.title')}
        description={t('pages.admin.description')}
        icon={<Settings className="size-6" aria-hidden />}
        breadcrumbs={[{ label: t('nav.groups.staff') }]}
      />

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {MODULES.map((module) => (
          <li key={module.title}>
            <Card as="article" className="flex h-full flex-col">
              <span className="mb-3 flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <module.icon className="size-5" aria-hidden />
              </span>
              <h2 className="text-lg font-semibold">{module.title}</h2>
              <p className="mt-1 flex-1 text-ink-soft">{module.body}</p>
              {module.href && !USE_MOCKS ? (
                <a
                  href={module.href}
                  className="mt-4 inline-flex min-h-10 items-center justify-center gap-1.5 self-start rounded-lg border border-line px-3 text-sm font-semibold text-brand-800 hover:bg-brand-50"
                >
                  Open in Django admin
                  <ExternalLink className="size-4" aria-hidden />
                </a>
              ) : null}
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
