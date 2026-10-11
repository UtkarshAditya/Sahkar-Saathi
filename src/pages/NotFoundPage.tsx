import { FileQuestionMark, House, MessageSquareText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ButtonLink } from '@/components/common/Button';
import { EmptyState } from '@/components/common/EmptyState';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function NotFoundPage() {
  const { t } = useTranslation();
  useDocumentTitle(t('pages.notFound.title'));
  return (
    <div className="py-10">
      <h1 className="sr-only">{t('pages.notFound.title')}</h1>
      <EmptyState
        icon={<FileQuestionMark className="size-6" aria-hidden />}
        title={t('pages.notFound.title')}
        description={t('pages.notFound.description')}
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <ButtonLink to="/" variant="primary" icon={<House className="size-5" aria-hidden />}>
              {t('header.home')}
            </ButtonLink>
            <ButtonLink to="/about" icon={<MessageSquareText className="size-5" aria-hidden />}>
              {t('nav.about')}
            </ButtonLink>
          </div>
        }
      />
    </div>
  );
}
