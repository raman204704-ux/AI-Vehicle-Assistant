import {
  ArrowUpRight,
  CircleHelp,
  MessageSquarePlus,
  Send,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  api,
  type DiagnosticMessage,
  type DiagnosticSession,
  type MechanicResponse,
  type Source,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  ErrorBanner,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "../components/Shared";
import { SourceList } from "./AssistantPage";

export function MechanicPage() {
  const { activeVehicle } = useVehicle();
  const activeVehicleId = activeVehicle?.id;
  const [sessions, setSessions] = useState<DiagnosticSession[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<DiagnosticMessage[]>([]);
  const [citations, setCitations] = useState<Record<number, Source[]>>({});
  const [question, setQuestion] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setSessions([]);
    setMessages([]);
    setSessionId(null);
    setCitations({});
    if (!activeVehicleId) return;
    setLoadingSessions(true);
    api<DiagnosticSession[]>(
      `/mechanic/vehicles/${activeVehicleId}/sessions`,
    )
      .then((result) => {
        if (cancelled) return;
        setSessions(result);
        setSessionId(result[0]?.id ?? null);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Could not load conversations",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingSessions(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeVehicleId]);

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) {
      setMessages([]);
      return;
    }
    setLoadingMessages(true);
    api<DiagnosticMessage[]>(`/mechanic/sessions/${sessionId}/messages`)
      .then((result) => {
        if (!cancelled) setMessages(result);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Could not load messages",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingMessages(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function refreshSessions(vehicleId: number) {
    const result = await api<DiagnosticSession[]>(
      `/mechanic/vehicles/${vehicleId}/sessions`,
    );
    setSessions(result);
  }

  async function sendQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVehicle || question.trim().length < 3) return;
    const submittedQuestion = question.trim();
    setSending(true);
    setError("");
    setQuestion("");
    setMessages((current) => [
      ...current,
      {
        id: -Date.now(),
        role: "user",
        content: submittedQuestion,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const result = await api<MechanicResponse>(
        `/mechanic/vehicles/${activeVehicle.id}/ask`,
        {
          method: "POST",
          body: JSON.stringify({
            question: submittedQuestion,
            session_id: sessionId,
          }),
        },
      );
      setSessionId(result.session_id);
      const history = await api<DiagnosticMessage[]>(
        `/mechanic/sessions/${result.session_id}/messages`,
      );
      setMessages(history);
      const lastAssistant = history
        .filter((message) => message.role === "assistant")
        .at(-1);
      if (lastAssistant && result.sources.length) {
        setCitations((current) => ({
          ...current,
          [lastAssistant.id]: result.sources,
        }));
      }
      await refreshSessions(activeVehicle.id);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "The mechanic assistant is unavailable",
      );
      setMessages((current) =>
        current.filter(
          (message) =>
            !(message.id < 0 && message.content === submittedQuestion),
        ),
      );
      setQuestion(submittedQuestion);
    } finally {
      setSending(false);
    }
  }

  function startNewConversation() {
    setSessionId(null);
    setMessages([]);
    setCitations({});
    setError("");
  }

  const selectedSession = sessions.find((session) => session.id === sessionId);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle?.vehicle_name ?? "TROUBLESHOOTING"}
        title="Let’s work through it."
        description="Describe what you’re noticing. The assistant will use your vehicle details and relevant sources."
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {!activeVehicle ? (
        <div className="panel">
          <div className="empty-garage">
            <CircleHelp size={25} />
            <h2>Select a vehicle to start</h2>
            <p>Your vehicle profile helps keep troubleshooting specific.</p>
          </div>
        </div>
      ) : (
        <div className="mechanic-layout">
          <aside className="conversation-sidebar panel">
            <div className="conversation-heading">
              <div>
                <p className="eyebrow">YOUR CHATS</p>
                <h2>Conversations</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Start a new conversation"
                onClick={startNewConversation}
              >
                <MessageSquarePlus size={18} />
              </button>
            </div>
            <button
              className={`new-chat-button ${sessionId === null ? "selected" : ""}`}
              onClick={startNewConversation}
            >
              <MessageSquarePlus size={16} /> New conversation
            </button>
            {loadingSessions ? (
              <LoadingState label="Loading chats..." />
            ) : sessions.length ? (
              <div className="conversation-list">
                {sessions.map((session) => (
                  <button
                    className={`conversation-item ${session.id === sessionId ? "selected" : ""}`}
                    key={session.id}
                    onClick={() => {
                      setError("");
                      setSessionId(session.id);
                    }}
                  >
                    <span className="conversation-item-icon">
                      <CircleHelp size={16} />
                    </span>
                    <span>
                      <strong>{session.title || "Vehicle question"}</strong>
                      <small>
                        {new Date(session.updated_at).toLocaleDateString()}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="conversation-empty">
                Your troubleshooting conversations will appear here.
              </p>
            )}
            <div className="conversation-safety">
              <ShieldAlert size={16} />
              <p>
                If braking or steering feels unsafe, pull over safely and call
                roadside assistance.
              </p>
            </div>
          </aside>

          <section className="chat-panel panel">
            <div className="chat-topline">
              <span className="assistant-avatar"><Sparkles size={18} /></span>
              <span>
                <strong>AI mechanic</strong>
                <small>
                  {activeVehicle.year} {activeVehicle.manufacturer}{" "}
                  {activeVehicle.model}
                </small>
              </span>
              {selectedSession && (
                <span className="chat-session-badge">
                  <StatusBadge status={selectedSession.status} />
                </span>
              )}
            </div>
            <div className="chat-messages">
              {loadingMessages ? (
                <LoadingState label="Opening conversation..." />
              ) : messages.length ? (
                messages.map((message) => (
                  <article
                    className={`chat-message ${message.role}`}
                    key={message.id}
                  >
                    {message.role === "assistant" && (
                      <span className="message-avatar"><Sparkles size={14} /></span>
                    )}
                    <div className="message-content">
                      <div className="message-bubble">{message.content}</div>
                      <small>
                        {new Date(message.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </small>
                      {message.role === "assistant" &&
                        citations[message.id]?.length > 0 && (
                          <div className="message-citations">
                            <strong>Sources</strong>
                            <SourceList sources={citations[message.id]} />
                          </div>
                        )}
                    </div>
                  </article>
                ))
              ) : (
                <div className="chat-welcome">
                  <span className="chat-welcome-icon"><CircleHelp size={23} /></span>
                  <h2>What’s going on with your vehicle?</h2>
                  <p>
                    Share a symptom or question. I’ll help you think through
                    possibilities and safe next steps — not make a confirmed
                    diagnosis.
                  </p>
                  <div className="chat-suggestions">
                    {[
                      "I hear a squeak when braking",
                      "The engine is slow to start",
                      "What should I check before a trip?",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => setQuestion(suggestion)}
                      >
                        {suggestion} <ArrowUpRight size={13} />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {sending && (
                <div className="chat-thinking">
                  <span className="message-avatar"><Sparkles size={14} /></span>
                  <div className="thinking-bubble">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            <form className="chat-compose" onSubmit={sendQuestion}>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Describe the symptom or ask a question..."
                rows={2}
                maxLength={2000}
                disabled={sending}
              />
              <div className="chat-compose-footer">
                <span>AI suggestions can be wrong. Use a qualified mechanic for urgent issues.</span>
                <button
                  className="button primary send-button"
                  disabled={sending || question.trim().length < 3}
                  aria-label="Send message"
                >
                  {sending ? "Thinking..." : "Send"} <Send size={15} />
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
