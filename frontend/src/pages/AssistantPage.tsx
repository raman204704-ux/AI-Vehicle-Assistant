import { ArrowUpRight, Bot, BookOpenCheck, Send, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type AssistantResponse, type Source } from "../api";
import { useVehicle } from "../components/AppShell";
import {
  ErrorBanner,
  LoadingState,
  PageHeader,
  Panel,
} from "../components/Shared";

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) {
    return (
      <p className="source-note">
        No reliable source links were available for this response.
      </p>
    );
  }
  return (
    <div className="source-list">
      {sources.map((source) => (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="source-card"
          key={source.source_id}
        >
          <span className="source-index">{source.source_id}</span>
          <span>
            <strong>{source.title}</strong>
            <small>
              {source.source_type} ·{" "}
              {source.url.replace(/^https?:\/\//, "").split("/")[0]}
            </small>
          </span>
          <ArrowUpRight size={16} />
        </a>
      ))}
    </div>
  );
}

export function AssistantPage() {
  const { activeVehicle } = useVehicle();
  const [question, setQuestion] = useState("");
  const [engine, setEngine] = useState("");
  const [market, setMarket] = useState("");
  const [answer, setAnswer] = useState<AssistantResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVehicle) return;
    setLoading(true);
    setError("");
    setAnswer(null);
    try {
      const result = await api<AssistantResponse>(
        `/assistant/vehicles/${activeVehicle.id}/ask`,
        {
          method: "POST",
          body: JSON.stringify({
            question: question.trim(),
            engine: engine.trim() || null,
            market: market.trim() || null,
          }),
        },
      );
      setAnswer(result);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "The assistant could not answer",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle?.vehicle_name ?? "VEHICLE-SPECIFIC ANSWERS"}
        title="Ask with your vehicle in mind."
        description="Search for maintenance information grounded in sources, with links you can inspect yourself."
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <div className="assistant-layout">
        <Panel className="assistant-form-panel">
          {!activeVehicle ? (
            <div className="inline-empty">
              <Bot size={22} />
              <div>
                <strong>Add a vehicle to begin</strong>
                <p>Answers are tailored to the active vehicle in your garage.</p>
              </div>
            </div>
          ) : (
            <form className="form-stack" onSubmit={ask}>
              <div className="ai-context-card">
                <span className="ai-context-icon"><Sparkles size={17} /></span>
                <span>
                  <small>ANSWERING FOR</small>
                  <strong>
                    {activeVehicle.year} {activeVehicle.manufacturer}{" "}
                    {activeVehicle.model} · {activeVehicle.fuel_type}
                  </strong>
                </span>
              </div>
              <label className="field">
                <span>Your maintenance question</span>
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="What should I know about my next scheduled service?"
                  rows={5}
                  minLength={5}
                  maxLength={1000}
                  required
                />
                <small className="field-hint">
                  Be specific about the symptom, part, or maintenance task.
                </small>
              </label>
              <div className="form-grid two">
                <label className="field">
                  <span>Engine (optional)</span>
                  <input
                    value={engine}
                    onChange={(event) => setEngine(event.target.value)}
                    placeholder="e.g. 1.5L diesel"
                    maxLength={100}
                  />
                </label>
                <label className="field">
                  <span>Country or market (optional)</span>
                  <input
                    value={market}
                    onChange={(event) => setMarket(event.target.value)}
                    placeholder="e.g. India"
                    maxLength={100}
                  />
                </label>
              </div>
              <button
                className="button primary wide"
                disabled={loading || question.trim().length < 5}
              >
                {loading ? "Searching trusted sources..." : "Find an answer"}
                {!loading && <Send size={16} />}
              </button>
              <p className="form-note">
                Web results may be incomplete. Always verify safety-critical
                instructions with a qualified technician.
              </p>
            </form>
          )}
        </Panel>

        <Panel
          title="A thoughtful answer"
          subtitle="Vehicle-specific context, with source links"
          className="assistant-answer-panel"
        >
          {loading ? (
            <div className="assistant-loading">
              <LoadingState label="Looking for relevant vehicle information..." />
              <p>We’re checking available sources before putting together a response.</p>
            </div>
          ) : answer ? (
            <div className="answer-content">
              <div className="answer-question">
                <span><BookOpenCheck size={16} /></span>
                <p>{answer.question}</p>
              </div>
              <div className="answer-body">{answer.answer}</div>
              <div className="answer-sources">
                <div className="subsection-heading">
                  <div>
                    <h3>Sources</h3>
                    <p>{answer.sources.length} links used for this answer</p>
                  </div>
                  <span className="verified-mark"><BookOpenCheck size={16} /></span>
                </div>
                <SourceList sources={answer.sources} />
              </div>
              <p className="footnote">
                Retrieved {new Date(answer.generated_at).toLocaleString()} ·{" "}
                {answer.documents_retrieved} passages considered
              </p>
            </div>
          ) : (
            <div className="answer-placeholder">
              <span className="answer-placeholder-icon"><Bot size={25} /></span>
              <h3>Good questions deserve good context.</h3>
              <p>
                Ask about a service interval, a maintenance task, or a vehicle
                component. Answers include sources so you can keep exploring.
              </p>
              <div className="prompt-suggestions">
                {[
                  "What should I check before a long trip?",
                  "How do I care for my car battery?",
                  "What does regular brake service include?",
                ].map((suggestion) => (
                  <button
                    type="button"
                    key={suggestion}
                    onClick={() => setQuestion(suggestion)}
                    disabled={!activeVehicle}
                  >
                    {suggestion} <ArrowUpRight size={14} />
                  </button>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

export { SourceList };
