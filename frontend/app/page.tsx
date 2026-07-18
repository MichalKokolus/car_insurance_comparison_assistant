"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Phase = "idle" | "running" | "awaiting" | "done" | "error";

interface InterruptData {
  missing_fields: string[];
  questions: Record<string, string>;
}

interface PolicyData {
  insurer: string | null;
  vehicle: string | null;
  coverage_type: "PZP" | "kasko";
  annual_premium: number | null;
  anniversary_date: string | null;
  notice_period_days: number | null;
}

interface ComparisonRow {
  insurer: string;
  product: string;
  annual_premium: number;
  premium_delta: number | null;
  glass_cover: boolean | null;
  animal_cover: boolean | null;
  comparable: boolean;
  notes: string | null;
}

interface ComparisonTable {
  rows: ComparisonRow[];
  summary: string | null;
}

interface ResearchQuery {
  query: string;
  sources: { title: string | null; url: string }[];
}

interface Recommendation {
  verdict: "switch" | "stay";
  rationale: string;
  estimated_annual_saving: number | null;
  cancellation_deadline: string | null;
  deadline_note: string;
  best_offer: { insurer: string; product: string; annual_premium: number } | null;
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const NODE_LABELS: Record<string, string> = {
  intake: "Extracted policy details",
  validate: "Validated required fields",
  market_research: "Researched market offers",
  coverage_compare: "Normalized like-for-like comparison",
  decision: "Computed recommendation + deadline",
  report: "Assembled final report",
};

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [prompt, setPrompt] = useState<InterruptData | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [policy, setPolicy] = useState<PolicyData | null>(null);
  const [researchLog, setResearchLog] = useState<ResearchQuery[]>([]);
  const [comparison, setComparison] = useState<ComparisonTable | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string>("");

  const esRef = useRef<EventSource | null>(null);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  useEffect(() => closeStream, [closeStream]);

  const openStream = useCallback(
    (id: string) => {
      closeStream();
      setPhase("running");
      const es = new EventSource(`/api/analysis/${id}/stream`);
      esRef.current = es;

      es.addEventListener("update", (e) => {
        const { node, state } = JSON.parse((e as MessageEvent).data);
        setSteps((prev) => [...prev, NODE_LABELS[node] ?? node]);
        if (node === "market_research" && Array.isArray(state?.research_log)) {
          setResearchLog(state.research_log);
        }
      });

      es.addEventListener("interrupt", (e) => {
        const data = JSON.parse((e as MessageEvent).data) as InterruptData;
        setPrompt(data);
        setPhase("awaiting");
        closeStream();
      });

      es.addEventListener("report", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setPolicy(data.policy ?? null);
        setComparison(data.comparison ?? null);
        setRecommendation(data.recommendation ?? null);
      });

      es.addEventListener("done", () => {
        setPhase("done");
        closeStream();
      });

      es.addEventListener("error", (e) => {
        const msg = (e as MessageEvent).data
          ? JSON.parse((e as MessageEvent).data).message
          : "stream error";
        setError(msg);
        setPhase("error");
        closeStream();
      });
    },
    [closeStream],
  );

  const analyze = useCallback(async () => {
    if (!file) return;
    setError("");
    setSteps([]);
    setPolicy(null);
    setResearchLog([]);
    setComparison(null);
    setRecommendation(null);
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/analysis", { method: "POST", body: form });
    if (!res.ok) {
      setError(`Upload failed (${res.status})`);
      setPhase("error");
      return;
    }
    const { thread_id } = await res.json();
    setThreadId(thread_id);
    openStream(thread_id);
  }, [file, openStream]);

  const submitAnswers = useCallback(async () => {
    if (!threadId) return;
    await fetch(`/api/analysis/${threadId}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    setPrompt(null);
    openStream(threadId);
  }, [threadId, answers, openStream]);

  return (
    <main>
      <h1>Car Insurance Comparison Assistant</h1>
      <p className="sub">
        Upload your current policy PDF. We extract it, research the market, and tell you whether to
        switch or stay — with the cancellation deadline.
      </p>

      <div className="panel">
        <div className="row">
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button onClick={analyze} disabled={!file || phase === "running"}>
            {phase === "running" && <span className="spinner light" />}
            {phase === "running" ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </div>

      {(steps.length > 0 || phase === "running") && (
        <div className="panel">
          <strong className="panel-title">Progress</strong>
          <ul className="steps">
            {steps.map((s, i) => (
              <li key={i} style={{ animationDelay: `${i * 40}ms` }}>
                <span className="tick">✓</span>
                {s}
              </li>
            ))}
            {phase === "running" && (
              <li className="pending">
                <span className="spinner" />
                Working…
              </li>
            )}
          </ul>
        </div>
      )}

      {phase === "awaiting" && prompt && (
        <div className="panel">
          <strong className="panel-title">A few details are missing</strong>
          {prompt.missing_fields.map((field) => (
            <div key={field}>
              <label htmlFor={field}>{prompt.questions[field]}</label>
              <input
                id={field}
                type="text"
                value={answers[field] ?? ""}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [field]: e.target.value }))}
              />
            </div>
          ))}
          <div style={{ marginTop: 16 }}>
            <button onClick={submitAnswers}>Continue</button>
          </div>
        </div>
      )}

      {policy && (
        <div className="panel">
          <strong className="panel-title">Your current policy</strong>
          <div className="table-wrap">
            <table className="kv">
              <tbody>
                <tr>
                  <th>Insurer</th>
                  <td>{policy.insurer ?? "—"}</td>
                </tr>
                <tr>
                  <th>Vehicle</th>
                  <td>{policy.vehicle ?? "—"}</td>
                </tr>
                <tr>
                  <th>Coverage</th>
                  <td>{policy.coverage_type}</td>
                </tr>
                <tr>
                  <th>Premium</th>
                  <td>
                    {policy.annual_premium != null ? `€${policy.annual_premium.toFixed(0)}/yr` : "—"}
                  </td>
                </tr>
                <tr>
                  <th>Anniversary</th>
                  <td>{policy.anniversary_date ?? "—"}</td>
                </tr>
                <tr>
                  <th>Notice period</th>
                  <td>
                    {policy.notice_period_days != null ? `${policy.notice_period_days} days` : "—"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {researchLog.length > 0 && (
        <div className="panel">
          <strong className="panel-title">Web search sources</strong>
          <ul className="research">
            {researchLog.map((q, i) => (
              <li key={i}>
                <div className="query">&ldquo;{q.query}&rdquo;</div>
                {q.sources.length > 0 ? (
                  <ul className="sources">
                    {q.sources.map((s, j) => (
                      <li key={j}>
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title || hostnameOf(s.url)}
                        </a>
                        <span className="domain"> — {hostnameOf(s.url)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="domain">no results</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {comparison && comparison.rows.length > 0 && (
        <div className="panel">
          <strong className="panel-title">Market comparison</strong>
          <div className="table-wrap">
            <table className="compare">
              <thead>
                <tr>
                  <th>Insurer</th>
                  <th>Product</th>
                  <th>Premium</th>
                  <th>Δ vs current</th>
                  <th>Glass</th>
                  <th>Animal</th>
                  <th>Comparable</th>
                </tr>
              </thead>
              <tbody>
                {comparison.rows.map((row, i) => (
                  <tr key={i} className={row.comparable ? undefined : "not-comparable"}>
                    <td>{row.insurer}</td>
                    <td>{row.product}</td>
                    <td>€{row.annual_premium.toFixed(0)}</td>
                    <td>
                      {row.premium_delta == null
                        ? "—"
                        : `€${row.premium_delta > 0 ? "+" : ""}${row.premium_delta.toFixed(0)}`}
                    </td>
                    <td className="center">{row.glass_cover ? "✓" : "✗"}</td>
                    <td className="center">{row.animal_cover ? "✓" : "✗"}</td>
                    <td className="center">{row.comparable ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {comparison.summary && <p className="summary">{comparison.summary}</p>}
        </div>
      )}

      {recommendation && (
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong className="panel-title">Recommendation</strong>
            <span className={`verdict ${recommendation.verdict}`}>
              {recommendation.verdict.toUpperCase()}
            </span>
          </div>
          <p>{recommendation.rationale}</p>
          {recommendation.best_offer && (
            <p>
              Best offer: <strong>{recommendation.best_offer.insurer}</strong> (
              {recommendation.best_offer.product}) — €
              {recommendation.best_offer.annual_premium.toFixed(0)}/yr
            </p>
          )}
          {recommendation.cancellation_deadline && (
            <p>
              Cancellation deadline: <strong>{recommendation.cancellation_deadline}</strong>
            </p>
          )}
          <p style={{ color: "var(--muted)" }}>{recommendation.deadline_note}</p>
        </div>
      )}

      {phase === "error" && <p className="error">Error: {error}</p>}
    </main>
  );
}
