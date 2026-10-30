import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CircleAlert, FileText, RotateCcw, SquarePen, WifiOff, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { SuggestedQuestions } from '@/components/chat/SuggestedQuestions';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { Button } from '@/components/common/Button';
import { Modal } from '@/components/common/Modal';
import { buildDemoConversation, makeId, SUGGESTED_QUESTIONS } from '@/data/mockChat';
import { MOCK_DOCUMENTS } from '@/data/mockDocuments';
import { stateName } from '@/data/options';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useSettings } from '@/hooks/useSettings';
import { useSpeechPlayback } from '@/hooks/useSpeechPlayback';
import { api, MOCK_ERROR_TRIGGER, USE_MOCKS } from '@/services/api';
import type { ChatMessage, SuggestedQuestion } from '@/types';

/** The four starter questions on the empty conversation, in the interface language. */
const STARTERS: Array<Pick<SuggestedQuestion, 'id' | 'topic'>> = [
  { id: 'q1', topic: 'law' },
  { id: 'q2', topic: 'law' },
  { id: 'q3', topic: 'pmfby' },
  { id: 'q4', topic: 'grievance' },
];

function scrollToEnd() {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollTo({
    top: document.documentElement.scrollHeight,
    behavior: reduce ? 'auto' : 'smooth',
  });
}

export default function AskPage() {
  const { t } = useTranslation();
  const { language, stateCode, setStateCode } = useSettings();
  const speechPlayback = useSpeechPlayback();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  useDocumentTitle(t('pages.ask.title'));

  // The example conversation is shown up front only in mock mode; with the real API it
  // stays one click away ("Show example conversation").
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    USE_MOCKS ? buildDemoConversation() : [],
  );
  const [input, setInput] = useState(() => params.get('q') ?? '');
  const [loading, setLoading] = useState(false);
  const [failedText, setFailedText] = useState<string | null>(null);
  const [failedFromVoice, setFailedFromVoice] = useState(false);
  const [failedOffline, setFailedOffline] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [confirmNewChat, setConfirmNewChat] = useState(false);
  const shouldScroll = useRef(false);

  // "Ask about this" links arrive as /?q=…&doc=…. Prefill (never auto-send).
  const docId = params.get('doc');
  const limitedDoc = useMemo(() => MOCK_DOCUMENTS.find((d) => d.id === docId) ?? null, [docId]);
  useEffect(() => {
    const q = params.get('q');
    if (q) setInput(q);
  }, [params]);

  useEffect(() => {
    if (shouldScroll.current) {
      scrollToEnd();
      shouldScroll.current = false;
    }
  }, [messages, loading]);

  const starters = useMemo<SuggestedQuestion[]>(
    () => STARTERS.map((q) => ({ ...q, text: t(`chat.examples.${q.id}`) })),
    [t],
  );

  async function ask(text: string, overrideState?: string, fromVoice = false) {
    const userMessage: ChatMessage = { id: makeId('u'), role: 'user', text };
    shouldScroll.current = true;
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
      shouldScroll.current = true;
      setMessages((prev) => [...prev, reply]);
    } catch {
      setFailedText(text);
      setFailedFromVoice(fromVoice);
      setFailedOffline(typeof navigator !== 'undefined' && navigator.onLine === false);
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

  function retry() {
    if (!failedText) return;
    // Remove the failed user message before retrying.
    setMessages((prev) => prev.slice(0, -1));
    void ask(
      failedText === MOCK_ERROR_TRIGGER ? SUGGESTED_QUESTIONS[2].text : failedText,
      undefined,
      failedFromVoice,
    );
  }

  function clearConversation() {
    speechPlayback.clear();
    setMessages([]);
    setConversationId(null);
    setFailedText(null);
    setFailedFromVoice(false);
    setConfirmNewChat(false);
  }

  function clearDocLimit() {
    const next = new URLSearchParams(params);
    next.delete('doc');
    next.delete('q');
    setParams(next, { replace: true });
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
      <h1 className="sr-only">{t('pages.ask.title')}</h1>

      {!isEmpty && (
        <div className="flex justify-end pt-3">
          <Button
            variant="ghost"
            size="sm"
            icon={<SquarePen className="size-4" aria-hidden />}
            onClick={() => setConfirmNewChat(true)}
            disabled={loading}
          >
            {t('chat.newChat')}
          </Button>
        </div>
      )}

      {isEmpty ? (
        <section
          aria-labelledby="welcome-heading"
          className="flex flex-1 flex-col justify-center py-10 sm:py-16"
        >
          <h2
            id="welcome-heading"
            className="text-center text-2xl font-semibold tracking-tight sm:text-3xl"
          >
            {t('chat.welcomeTitle')}
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-center text-ink-soft">{t('chat.welcomeBody')}</p>
          <div className="mt-8">
            <SuggestedQuestions
              title={t('chat.suggested')}
              questions={starters}
              onSelect={(text) => void ask(text)}
              disabled={loading}
            />
          </div>
          <div className="mt-4 flex justify-center">
            <Button
              variant="ghost"
              size="sm"
              icon={<RotateCcw className="size-4" aria-hidden />}
              onClick={() => setMessages(buildDemoConversation())}
            >
              Show example conversation
            </Button>
          </div>
        </section>
      ) : (
        <div className="flex flex-1 flex-col gap-8 py-6" aria-live="polite">
          {messages[0]?.id.startsWith('demo-') && (
            <p className="text-center text-xs font-medium text-ink-muted">
              Example conversation · demonstration only
            </p>
          )}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              disabled={loading}
              onFollowup={handleFollowup}
              onChooseState={handleChooseState}
              speech={speechPlayback}
              language={language}
            />
          ))}

          {loading && <TypingIndicator />}

          {failedText && !loading && (
            <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
              <span className="flex items-center gap-1.5 font-semibold text-red-800">
                {failedOffline ? (
                  <WifiOff className="size-4" aria-hidden />
                ) : (
                  <CircleAlert className="size-4" aria-hidden />
                )}
                {t('chat.errorTitle')}
              </span>
              <span className="text-ink-soft">
                {failedOffline ? t('chat.offlineBody') : t('chat.errorBody')}
              </span>
              <Button
                variant="secondary"
                size="sm"
                icon={<RotateCcw className="size-4" aria-hidden />}
                onClick={retry}
              >
                {t('common.retry')}
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 bg-canvas pt-2 pb-3 lg:bottom-0 lg:pb-4">
        {limitedDoc && (
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-1 text-sm text-brand-900">
            <FileText className="size-4 shrink-0" aria-hidden />
            <span className="min-w-0 flex-1 truncate">
              {t('chat.limitedTo')}: <strong>{limitedDoc.title}</strong>
            </span>
            <button
              type="button"
              onClick={clearDocLimit}
              className="flex size-11 items-center justify-center rounded hover:bg-brand-100 lg:size-8"
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
          prominentMic={isEmpty}
        />
      </div>

      <Modal
        open={confirmNewChat}
        onClose={() => setConfirmNewChat(false)}
        title={t('chat.newChatConfirmTitle')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmNewChat(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={clearConversation}>{t('chat.newChat')}</Button>
          </>
        }
      >
        <p className="text-ink-soft">{t('chat.newChatConfirmBody')}</p>
      </Modal>
    </div>
  );
}
