import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { FileText, LoaderCircle, Menu, MoreHorizontal, Trash, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ChatInput } from '@/components/chat/ChatInput';
import { CitationPanel } from '@/components/chat/CitationPanel';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { SuggestedQuestions } from '@/components/chat/SuggestedQuestions';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Modal } from '@/components/common/Modal';
import { Notice } from '@/components/common/Notice';
import { buildDemoConversation, makeId, SUGGESTED_QUESTIONS } from '@/data/mockChat';
import { MOCK_DOCUMENTS } from '@/data/mockDocuments';
import { stateName } from '@/data/options';
import { useSettings } from '@/hooks/useSettings';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useSpeechPlayback } from '@/hooks/useSpeechPlayback';
import { LANGUAGES } from '@/i18n';
import { api, MOCK_ERROR_TRIGGER, USE_MOCKS } from '@/services/api';
import type { ChatMessage } from '@/types';

export default function AskPage() {
  const { t } = useTranslation();
  const { language, stateCode, setStateCode } = useSettings();
  const speechPlayback = useSpeechPlayback();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(() => params.get('q') ?? '');
  const [loading, setLoading] = useState(false);
  const [failedText, setFailedText] = useState<string | null>(null);
  const [failedFromVoice, setFailedFromVoice] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [transcriptReviewVersion, setTranscriptReviewVersion] = useState(0);
  const [showExampleConversation, setShowExampleConversation] = useState(false);
  const conversationRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const wasNearBottom = useRef(true);
  const forceScroll = useRef(false);

  useDocumentTitle(t('pages.ask.title'));
  // "Ask about this" links arrive as /?q=…&doc=…. Prefill (never auto-send).
  const docId = params.get('doc');
  const limitedDoc = MOCK_DOCUMENTS.find((d) => d.id === docId) ?? null;
  const selectedCitations = useMemo(
    () => messages.find((message) => message.id === selectedId)?.response?.citations ?? null,
    [messages, selectedId],
  );
  useEffect(() => {
    const q = params.get('q');
    if (q) setInput(q);
  }, [params]);

  useEffect(() => {
    if (!forceScroll.current && !wasNearBottom.current) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    endRef.current?.scrollIntoView({
      behavior: reducedMotion ? 'auto' : 'smooth',
      block: 'end',
    });
    wasNearBottom.current = true;
    forceScroll.current = false;
  }, [failedText, loading, messages, transcriptReviewVersion]);

  const handleTranscriptReview = useCallback(() => {
    setTranscriptReviewVersion((version) => version + 1);
  }, []);

  function handleConversationScroll() {
    const element = conversationRef.current;
    if (!element) return;
    wasNearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
  }

  async function ask(text: string, overrideState?: string, fromVoice = false) {
    const userMessage: ChatMessage = { id: makeId('u'), role: 'user', text };
    forceScroll.current = true;
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setFailedText(null);
    setFailedFromVoice(false);
    setLoading(true);
    try {
      const response = await api.ask({
        conversation_id: conversationId,
        text,
        language,
        state: overrideState ?? stateCode,
        document_id: limitedDoc?.id ?? null,
      });
      setConversationId(response.conversation_id);
      const reply: ChatMessage = {
        id: response.message_id,
        role: 'assistant',
        text: '',
        response,
        speechLanguage: language,
        autoPlaySpeech: fromVoice,
        pendingQuestion: response.needs_state ? text : undefined,
      };
      forceScroll.current = false;
      setMessages((prev) => [...prev, reply]);
      if (response.citations.length > 0) setSelectedId(reply.id);
    } catch {
      setFailedText(text);
      setFailedFromVoice(fromVoice);
    } finally {
      setLoading(false);
    }
  }

  function handleChooseState(messageId: string, code: string) {
    const original = messages.find((m) => m.id === messageId)?.pendingQuestion;
    setStateCode(code);
    // The prompt is answered: drop it so the picker does not show again.
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, pendingQuestion: undefined } : m)),
    );
    if (original) void ask(`${original} (State: ${stateName(code)})`, code);
  }

  function handleFollowup(text: string) {
    if (text === 'Open the Grievance helper') {
      navigate('/grievance');
      return;
    }
    void ask(text);
  }

  function clearConversation() {
    speechPlayback.clear();
    forceScroll.current = true;
    setMessages([]);
    setConversationId(null);
    setSelectedId(null);
    setFailedText(null);
    setFailedFromVoice(false);
    setShowExampleConversation(false);
    setClearConfirmOpen(false);
  }

  function clearDocLimit() {
    const next = new URLSearchParams(params);
    next.delete('doc');
    next.delete('q');
    setParams(next, { replace: true });
  }

  const isEmpty = messages.length === 0;
  const activeLanguage = LANGUAGES.find((item) => item.code === language);

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-line px-3 py-2 sm:px-6 max-[20rem]:px-2 max-[20rem]:py-1">
        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
          <h1 className="min-w-0 text-lg font-bold leading-tight sm:text-xl max-[20rem]:text-base">
            {t('pages.ask.title')}
          </h1>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <Badge tone="brand">{activeLanguage?.label ?? language}</Badge>
            <Button
              variant="secondary"
              size="sm"
              className="min-h-12"
              icon={<MoreHorizontal className="size-4" aria-hidden />}
              onClick={() => setMoreOpen(true)}
            >
              {t('chat.more')}
            </Button>
          </div>
        </div>
        <p className="mt-1 text-xs leading-snug text-ink-muted sm:text-sm max-[20rem]:mt-0.5 max-[20rem]:text-[10px]">
          {t(USE_MOCKS ? 'chat.demoLegalLine' : 'chat.legalLine')}{' '}
          <Link to="/about" className="font-semibold text-brand-800 underline underline-offset-2">
            {t('chat.learnMore')}
          </Link>
        </p>
        <details className="group mt-1 text-sm max-[20rem]:hidden">
          <summary className="flex min-h-12 w-fit cursor-pointer list-none items-center font-semibold text-brand-800 underline underline-offset-2 focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-saffron-700 [&::-webkit-details-marker]:hidden">
            {t('chat.howAnswersWork')}
          </summary>
          <p className="max-w-3xl pb-2 text-ink-soft">{t('chat.howAnswersWorkBody')}</p>
        </details>
      </header>

      <div
        ref={conversationRef}
        role="log"
        aria-label={t('chat.conversation')}
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={handleConversationScroll}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-6"
      >
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
          {isEmpty ? (
            <section className="mx-auto w-full max-w-3xl py-4 sm:py-8">
              <h2 className="text-xl font-bold text-brand-900">{t('chat.welcomeTitle')}</h2>
              <p className="mt-2 text-ink-soft">{t('chat.welcomeBody')}</p>
              <div className="mt-5">
                <SuggestedQuestions
                  title={t('chat.suggested')}
                  questions={SUGGESTED_QUESTIONS.slice(0, 4)}
                  onSelect={(text) => void ask(text)}
                  disabled={loading}
                />
              </div>
            </section>
          ) : (
            <>
              {showExampleConversation && messages[0]?.id.startsWith('demo-') && (
                <p className="text-center text-xs font-semibold text-ink-muted">
                  {t('chat.exampleConversation')}
                </p>
              )}
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  selected={message.id === selectedId}
                  disabled={loading}
                  onViewSources={(messageId) => {
                    setSelectedId(messageId);
                    setSourcesOpen(true);
                  }}
                  onFollowup={handleFollowup}
                  onChooseState={handleChooseState}
                  speech={speechPlayback}
                  language={language}
                />
              ))}

              {loading && (
                <div role="status" className="flex items-center gap-2 text-ink-muted">
                  <LoaderCircle className="size-5 animate-spin text-brand-700" aria-hidden />
                  {t('chat.sending')}
                </div>
              )}

              {failedText && (
                <Notice tone="warning" role="alert" title={t('chat.errorTitle')}>
                  <p>{t('chat.errorBody')}</p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-2 min-h-12"
                    onClick={() => {
                      setMessages((prev) => prev.slice(0, -1));
                      void ask(
                        failedText === MOCK_ERROR_TRIGGER
                          ? SUGGESTED_QUESTIONS[2].text
                          : failedText,
                        undefined,
                        failedFromVoice,
                      );
                    }}
                  >
                    {t('common.retry')}
                  </Button>
                </Notice>
              )}
            </>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="relative z-10 shrink-0 border-t border-line bg-surface px-3 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.06)] sm:px-6 max-[20rem]:pt-1 max-[20rem]:pb-1">
        {limitedDoc && (
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-1.5 text-sm text-brand-900">
            <FileText className="size-4 shrink-0" aria-hidden />
            <span className="min-w-0 flex-1 truncate">
              {t('chat.limitedTo')}: <strong>{limitedDoc.title}</strong>
            </span>
            <button
              type="button"
              onClick={clearDocLimit}
              className="flex min-h-12 min-w-12 items-center justify-center rounded hover:bg-brand-100"
              aria-label={t('chat.removeLimit')}
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
        )}
        {!isEmpty && (
          <div className="mb-2">
            <Button
              variant="ghost"
              size="sm"
              className="min-h-12"
              onClick={() => setExamplesOpen(true)}
              icon={<Menu className="size-4" aria-hidden />}
            >
              {t('chat.exampleQuestions')}
            </Button>
          </div>
        )}
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={(text, fromVoice) => void ask(text, undefined, fromVoice)}
          loading={loading}
          language={language}
          prominentMic
          onTranscriptReview={handleTranscriptReview}
        />
      </div>

      <Modal
        open={examplesOpen}
        onClose={() => setExamplesOpen(false)}
        title={t('chat.exampleQuestions')}
      >
        <SuggestedQuestions
          title={t('chat.suggested')}
          questions={SUGGESTED_QUESTIONS.slice(0, 4)}
          onSelect={(text) => {
            setExamplesOpen(false);
            void ask(text);
          }}
          disabled={loading}
        />
      </Modal>

      <Modal open={moreOpen} onClose={() => setMoreOpen(false)} title={t('chat.more')}>
        <div className="flex flex-col gap-3">
          <details className="hidden rounded-xl bg-canvas p-3 max-[20rem]:block">
            <summary className="min-h-12 cursor-pointer content-center font-semibold text-brand-800 underline underline-offset-2">
              {t('chat.howAnswersWork')}
            </summary>
            <p className="pb-2 text-sm text-ink-soft">{t('chat.howAnswersWorkBody')}</p>
          </details>
          {USE_MOCKS && (
            <Button
              variant="secondary"
              className="min-h-12 justify-start"
              onClick={() => {
                forceScroll.current = true;
                setMessages(buildDemoConversation());
                setSelectedId('demo-a1');
                setShowExampleConversation(true);
                setMoreOpen(false);
              }}
            >
              {t('chat.showExampleConversation')}
            </Button>
          )}
          <Button
            variant="secondary"
            className="min-h-12 justify-start"
            disabled={isEmpty || loading}
            icon={<Trash className="size-5" aria-hidden />}
            onClick={() => {
              setMoreOpen(false);
              setClearConfirmOpen(true);
            }}
          >
            {t('chat.clear')}
          </Button>
        </div>
      </Modal>

      <Modal
        open={sourcesOpen}
        onClose={() => setSourcesOpen(false)}
        title={t('chat.sources')}
        presentation="drawer"
      >
        <CitationPanel citations={selectedCitations} />
      </Modal>

      <Modal
        open={clearConfirmOpen}
        onClose={() => setClearConfirmOpen(false)}
        title={t('chat.clearConfirmTitle')}
      >
        <p className="text-ink-soft">{t('chat.clearConfirmBody')}</p>
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <Button
            variant="secondary"
            className="min-h-12"
            onClick={() => setClearConfirmOpen(false)}
          >
            {t('chat.keepConversation')}
          </Button>
          <Button
            variant="danger"
            className="min-h-12"
            onClick={clearConversation}
            icon={<Trash className="size-5" aria-hidden />}
          >
            {t('chat.confirmClear')}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
