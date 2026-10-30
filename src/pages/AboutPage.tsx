import { useId, useState, type FormEvent } from 'react';
import {
  BookOpen,
  CircleAlert,
  Eye,
  FileText,
  GraduationCap,
  Info,
  Languages,
  Lock,
  MessageSquareText,
  Phone,
  Scale,
  Search,
  ShieldCheck,
  Sprout,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { Button, ButtonLink } from '@/components/common/Button';
import { Card, CardTitle } from '@/components/common/Card';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { LANGUAGES } from '@/i18n';
import { api, ApiError, USE_MOCKS } from '@/services/api';

const HOW_IT_WORKS = [
  {
    icon: MessageSquareText,
    title: 'You ask',
    body: 'Type a question in your language.',
  },
  {
    icon: Search,
    title: 'It searches sources',
    body: 'It looks only in a small, checked set of public cooperative documents, filtered by your state.',
  },
  {
    icon: ShieldCheck,
    title: 'It checks the evidence',
    body: 'If the evidence is weak, or a claim has no source, it does not answer.',
  },
  {
    icon: FileText,
    title: 'You see the source',
    body: 'Every answer shows the document title, date and page, so you can check it.',
  },
];

const ASSISTANCE = [
  { icon: BookOpen, title: 'Cooperative law and by-laws', to: '/library' },
  { icon: Sprout, title: 'Crop insurance (PMFBY)', to: '/' },
  { icon: Scale, title: 'Grievance guidance', to: '/grievance' },
  { icon: GraduationCap, title: 'Financial literacy basics', to: '/learn' },
  { icon: MessageSquareText, title: 'General questions', to: '/' },
];

const LIMITS = [
  'It gives legal information, not legal advice, and never predicts the outcome of a dispute.',
  'It covers central cooperative documents and one chosen state, not every state Act.',
  'It supports English, Hindi and one regional language, not all 22 scheduled languages.',
  'It does not file complaints or applications on your behalf.',
  'Documents can change. Always check the date shown with each source.',
];

const FEEDBACK_TYPES = [
  'Wrong or outdated information',
  'Hard to understand',
  'Language problem',
  'Suggestion',
  'Other',
];

export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <>
      <PageHeader
        title={t('pages.about.title')}
        description={t('pages.about.description')}
        icon={<Info className="size-6" aria-hidden />}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card as="section" className="lg:col-span-2" aria-labelledby="overview">
          <h2 id="overview" className="text-xl font-semibold">
            What is Sahkar Saathi?
          </h2>
          <p className="mt-2 text-ink-soft">
            Sahkar Saathi is a prototype assistant for cooperative members, farmers and PACS
            secretaries. You can ask about cooperative laws and by-laws, crop insurance, schemes and
            member services, or get help preparing a grievance, in your own language. It is being
            built for Smart India Hackathon 2026 (problem statement 26088).
          </p>
          <p className="mt-2 text-ink-soft">
            The aim is simple: short answers that always show where they come from, and an honest “I
            could not find this” when the sources do not cover a question.
          </p>
        </Card>

        <Card as="section" aria-labelledby="languages">
          <CardTitle
            icon={<Languages className="size-5" aria-hidden />}
            title={<span id="languages">Languages</span>}
            description="Change the language from the menu at any time."
          />
          <ul className="flex flex-col gap-2">
            {LANGUAGES.map((lang) => (
              <li
                key={lang.code}
                className="flex items-center justify-between rounded-lg bg-canvas px-3 py-2"
              >
                <span lang={lang.code} className="font-semibold">
                  {lang.label}
                </span>
                <span className="text-sm text-ink-muted">{lang.englishLabel}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <section aria-labelledby="how" className="mt-8">
        <h2 id="how" className="mb-4 text-xl font-semibold">
          How it works
        </h2>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map((step, i) => (
            <li key={step.title} className="rounded-2xl border border-line bg-surface p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="flex size-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                  <step.icon className="size-5" aria-hidden />
                </span>
                <span className="text-sm font-bold text-saffron-700">Step {i + 1}</span>
              </div>
              <h3 className="font-semibold">{step.title}</h3>
              <p className="mt-1 text-sm text-ink-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="assistance" className="mt-8">
        <h2 id="assistance" className="mb-4 text-xl font-semibold">
          Help you can get
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ASSISTANCE.map((item) => (
            <li key={item.title}>
              <Link
                to={item.to}
                className="flex min-h-14 items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 font-medium hover:border-brand-300 hover:bg-brand-50"
              >
                <item.icon className="size-5 text-brand-700" aria-hidden />
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card as="section" aria-labelledby="limits">
          <CardTitle
            icon={<CircleAlert className="size-5" aria-hidden />}
            title={<span id="limits">What it cannot do</span>}
          />
          <ul className="flex list-disc flex-col gap-2 pl-5 text-ink-soft marker:text-saffron-500">
            {LIMITS.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        </Card>

        <Card as="section" aria-labelledby="privacy">
          <CardTitle
            icon={<Lock className="size-5" aria-hidden />}
            title={<span id="privacy">Your privacy</span>}
          />
          <ul className="flex list-disc flex-col gap-2 pl-5 text-ink-soft marker:text-brand-500">
            <li>No login or account is needed to ask questions.</li>
            <li>The service is designed not to store names, phone numbers or ID numbers.</li>
            <li>Conversations are kept anonymously only to measure and improve answer quality.</li>
            <li>Your language and state choices are saved on this device only.</li>
            <li>Grievance drafts stay in your browser unless you copy or download them.</li>
          </ul>
        </Card>

        <Card as="section" aria-labelledby="sources">
          <CardTitle
            icon={<Eye className="size-5" aria-hidden />}
            title={<span id="sources">Source transparency</span>}
          />
          <p className="text-ink-soft">
            The assistant searches a small set of public documents: the Multi-State Co-operative
            Societies Act, model by-laws, one state’s Act and rules, and scheme guidelines. Each has
            a recorded publisher, date and version, and outdated versions are retired, not silently
            replaced.
          </p>
          <ButtonLink
            to="/library"
            variant="secondary"
            className="mt-4"
            icon={<BookOpen className="size-5" aria-hidden />}
          >
            Open the law library
          </ButtonLink>
        </Card>

        <Card as="section" aria-labelledby="helplines">
          <CardTitle
            icon={<Phone className="size-5" aria-hidden />}
            title={<span id="helplines">Helplines</span>}
          />
          <Notice tone="warning" title="Not yet verified">
            Helpline numbers will be listed here only after the team verifies each one against an
            official source, with the date it was checked. Until then, contact your PACS, bank
            branch or district cooperative office.
          </Notice>
        </Card>
      </div>

      <FeedbackForm />
    </>
  );
}

interface FeedbackErrors {
  type?: string;
  message?: string;
}

function FeedbackForm() {
  const id = useId();
  const [type, setType] = useState('');
  const [message, setMessage] = useState('');
  const [page, setPage] = useState('');
  const [errors, setErrors] = useState<FeedbackErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  function validate(): FeedbackErrors {
    const next: FeedbackErrors = {};
    if (!type) next.type = 'Please choose what your feedback is about.';
    if (message.trim().length < 10) next.message = 'Please write at least 10 characters.';
    else if (message.length > 1000) next.message = 'Please keep it under 1000 characters.';
    else if (/\d{10}/.test(message.replace(/\s/g, '')))
      next.message = 'Please remove phone or ID numbers. We do not store personal details.';
    return next;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next = validate();
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setSubmitting(true);
    setSendError(null);
    try {
      await api.sendFeedback({
        message_id: null,
        rating: null,
        comment: message,
        reason: `${type}${page ? ` · ${page}` : ''}`.slice(0, 100),
      });
      setSubmitted(true);
    } catch (err) {
      setSendError(
        err instanceof ApiError && err.code === 'rate_limited'
          ? 'Too many messages in a short time. Please wait a minute and try again.'
          : 'Could not send your feedback. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card as="section" aria-labelledby={`${id}-heading`} className="mt-8">
      <CardTitle
        icon={<MessageSquareText className="size-5" aria-hidden />}
        title={<span id={`${id}-heading`}>Send feedback</span>}
        description="Tell us what was wrong or confusing. Do not include personal details."
      />
      {submitted ? (
        <div className="flex flex-col items-start gap-3">
          <Notice tone="success" role="status" title="Thank you for your feedback">
            {USE_MOCKS
              ? 'In this demo it is not sent anywhere. With the backend connected it reaches the review queue.'
              : 'It has reached the team’s review queue.'}
          </Notice>
          <Button
            variant="secondary"
            onClick={() => {
              setSubmitted(false);
              setType('');
              setMessage('');
              setPage('');
            }}
          >
            Send more feedback
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor={`${id}-type`} className="field-label">
              About <span className="text-red-700">*</span>
            </label>
            <select
              id={`${id}-type`}
              className="field-input"
              value={type}
              onChange={(e) => setType(e.target.value)}
              aria-invalid={Boolean(errors.type)}
              aria-describedby={errors.type ? `${id}-type-error` : undefined}
            >
              <option value="">Choose…</option>
              {FEEDBACK_TYPES.map((ft) => (
                <option key={ft}>{ft}</option>
              ))}
            </select>
            {errors.type && (
              <p id={`${id}-type-error`} className="field-error">
                {errors.type}
              </p>
            )}
          </div>
          <div>
            <label htmlFor={`${id}-page`} className="field-label">
              Which page? (optional)
            </label>
            <input
              id={`${id}-page`}
              className="field-input"
              value={page}
              onChange={(e) => setPage(e.target.value)}
              maxLength={60}
              placeholder="e.g. Crop insurance guide"
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor={`${id}-message`} className="field-label">
              Your feedback <span className="text-red-700">*</span>
            </label>
            <textarea
              id={`${id}-message`}
              rows={4}
              className="field-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              aria-invalid={Boolean(errors.message)}
              aria-describedby={`${id}-message-hint`}
            />
            <div id={`${id}-message-hint`} className="flex justify-between gap-2">
              {errors.message ? <p className="field-error">{errors.message}</p> : <span />}
              <p className="field-hint">{message.length}/1000</p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-2 sm:col-span-2">
            {sendError && (
              <p role="alert" className="field-error">
                {sendError}
              </p>
            )}
            <Button type="submit" loading={submitting}>
              Send feedback
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
