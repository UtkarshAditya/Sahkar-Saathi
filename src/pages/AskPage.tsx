import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { FileText, LoaderCircle, MessageSquareText, RotateCcw, Trash, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ChatInput } from '@/components/chat/ChatInput';
import { CitationPanel } from '@/components/chat/CitationPanel';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { SuggestedQuestions } from '@/components/chat/SuggestedQuestions';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { SUGGESTED_QUESTIONS } from '@/data/suggestedQuestions';
import { stateName } from '@/data/options';
import { makeId } from '@/lib/format';
import { useSettings } from '@/hooks/useSettings';
import { useSpeechPlayback } from '@/hooks/useSpeechPlayback';
import { api, apiErrorTranslationKey, MOCK_ERROR_TRIGGER, USE_MOCKS } from '@/services/api';
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
  const [failedErrorKey, setFailedErrorKey] = useState('chat.errorBody');
  const [failedFromVoice, setFailedFromVoice] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const shouldScroll = useRef(false);
  const userInteractedRef = useRef(false);
  const askControllerRef = useRef<AbortController | null>(null);
  const askInFlightRef = useRef(false);

  useEffect(
    () => () => {
      askControllerRef.current?.abort();
    },
    [],
  );

  // "Ask about this" links arrive as /?q=…&doc=…. Prefill (never auto-send).
  const docId = params.get('doc');
  const limitedDoc = docId ? { id: docId, title: params.get('docTitle') ?? docId } : null;

  useEffect(() => {
    if (!USE_MOCKS) return;
    let active = true;
    void import('@/data/mockChat').then(({ buildDemoConversation }) => {
      if (!active || userInteractedRef.current) return;
      setMessages(buildDemoConversation());
      setSelectedId('demo-a1');
    });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const q = params.get('q');
    if (q) setInput(q);
  }, [params]);

  useEffect(() => {
    if (shouldScroll.current) {
      endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      shouldScroll.current = false;
    }
  }, [messages, loading]);

  const selectedCitations = useMemo(
    () => messages.find((m) => m.id === selectedId)?.response?.citations ?? null,
    [messages, selectedId],
  );

  async function ask(text: string, overrideState?: string, fromVoice = false) {
    if (askInFlightRef.current) return;
    userInteractedRef.current = true;
    const controller = new AbortController();
    askControllerRef.current = controller;
    askInFlightRef.current = true;
    const userMessage: ChatMessage = { id: makeId('u'), role: 'user', text };
    shouldScroll.current = true;
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setFailedText(null);
    setFailedErrorKey('chat.errorBody');
    setFailedFromVoice(false);
    setLoading(true);
    try {
      const response = await api.ask(
        {
          conversation_id: conversationId,
          text,
          language,
          state: overrideState ?? stateCode,
          document_id: limitedDoc?.id ?? null,
        },
        controller.signal,
      );
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
      shouldScroll.current = true;
      setMessages((prev) => [...prev, reply]);
      if (response.citations.length > 0) setSelectedId(reply.id);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setFailedText(text);
      setFailedErrorKey(apiErrorTranslationKey(cause));
      setFailedFromVoice(fromVoice);
    } finally {
      askInFlightRef.current = false;
      askControllerRef.current = null;
      if (!controller.signal.aborted) setLoading(false);
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
    userInteractedRef.current = true;
    speechPlayback.clear();
    setMessages([]);
    setConversationId(null);
    setSelectedId(null);
    setFailedText(null);
    setFailedErrorKey('chat.errorBody');
    setFailedFromVoice(false);
  }

  async function showExampleConversation() {
    userInteractedRef.current = true;
    const { buildDemoConversation } = await import('@/data/mockChat');
    setMessages(buildDemoConversation());
    setSelectedId('demo-a1');
  }

  function clearDocLimit() {
    const next = new URLSearchParams(params);
    next.delete('doc');
    next.delete('docTitle');
    next.delete('q');
    setParams(next, { replace: true });
  }

  const isEmpty = messages.length === 0;

  return (
    <>
      <PageHeader
        title={t('pages.ask.title')}
        description={t('pages.ask.description')}
        icon={<MessageSquareText className="size-6" aria-hidden />}
        badges={<>{stateCode && <Badge tone="brand">{stateName(stateCode)}</Badge>}</>}
      />

      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card padding="none" className="flex min-w-0 flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
            <h2 className="font-semibold">{t('chat.conversation')}</h2>
            {isEmpty ? (
              USE_MOCKS && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="min-w-0 max-w-full"
                  icon={<RotateCcw className="size-4" aria-hidden />}
                  onClick={() => void showExampleConversation()}
                >
                  Show example conversation
                </Button>
              )
            ) : (
              <Button
                variant="ghost"
                size="sm"
                className="min-w-0 max-w-full"
                icon={<Trash className="size-4" aria-hidden />}
                onClick={clearConversation}
                disabled={loading}
              >
                {t('chat.clear')}
              </Button>
            )}
          </div>

          <div className="flex flex-1 flex-col gap-4 px-4 py-5 sm:px-5" aria-live="polite">
            <section className="rounded-2xl bg-brand-50 p-4 ring-1 ring-brand-100">
              <h2 className="text-lg font-semibold text-brand-900">{t('chat.welcomeTitle')}</h2>
              <p className="mt-1 text-ink-soft">{t('chat.welcomeBody')}</p>
              <div className="mt-4">
                <SuggestedQuestions
                  title={t('chat.suggested')}
                  questions={SUGGESTED_QUESTIONS.slice(0, 4)}
                  onSelect={(text) => void ask(text)}
                  disabled={loading}
                />
              </div>
            </section>

            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                selected={message.id === selectedId}
                disabled={loading}
                onViewSources={setSelectedId}
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
                <p>{t(failedErrorKey)}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    // Remove the failed user message before retrying.
                    setMessages((prev) => prev.slice(0, -1));
                    void ask(
                      failedText === MOCK_ERROR_TRIGGER ? SUGGESTED_QUESTIONS[2].text : failedText,
                      undefined,
                      failedFromVoice,
                    );
                  }}
                >
                  {t('common.retry')}
                </Button>
              </Notice>
            )}
            <div ref={endRef} />
          </div>

          <div className="sticky bottom-16 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:px-5 lg:bottom-0 lg:rounded-b-2xl">
            {limitedDoc && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-1.5 text-sm text-brand-900">
                <FileText className="size-4 shrink-0" aria-hidden />
                <span className="min-w-0 flex-1 truncate">
                  {t('chat.limitedTo')}: <strong>{limitedDoc.title}</strong>
                </span>
                <button
                  type="button"
                  onClick={clearDocLimit}
                  className="flex size-7 items-center justify-center rounded hover:bg-brand-100"
                  aria-label={t('chat.removeLimit')}
                >
                  <X className="size-4" aria-hidden />
                </button>
              </div>
            )}
            <ChatInput
              value={input}
              onChange={setInput}
              onSubmit={(text, fromVoice) => void ask(text, undefined, fromVoice)}
              loading={loading}
              language={language}
            />
          </div>
        </Card>

        <div className="hidden lg:block">
          <div className="sticky top-24 flex flex-col gap-4">
            <CitationPanel citations={selectedCitations} />
          </div>
        </div>
      </div>
    </>
  );
}
