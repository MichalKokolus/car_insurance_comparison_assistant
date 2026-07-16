"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Phase = "idle" | "running" | "awaiting" | "done" | "error";

interface InterruptData {
  missing_fields: string[];
  questions: Record<string, string>;
}

interface Recommendation {
  verdict: "switch" | "stay";
  rationale: string;
  estimated_annual_saving: number | null;
  cancellation_deadline: string | null;
  deadline_note: string;
  best_offer: { insurer: string; product: string; annual_premium: number } | null;
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
  const [report, setReport] = useState<string>("");
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
        const { node } = JSON.parse((e as MessageEvent).data);
        setSteps((prev) => [...prev, NODE_LABELS[node] ?? node]);
      });

      es.addEventListener("interrupt", (e) => {
        const data = JSON.parse((e as MessageEvent).data) as InterruptData;
        setPrompt(data);
        setPhase("awaiting");
        closeStream();
      });

      es.addEventListener("report", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setReport(data.report ?? "");
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
    setReport("");
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
            {phase === "running" ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </div>

      {steps.length > 0 && (
        <div className="panel">
          <strong>Progress</strong>
          <ul className="steps">
            {steps.map((s, i) => (
              <li key={i}>
                <span className="tick">✓</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase === "awaiting" && prompt && (
        <div className="panel">
          <strong>A few details are missing</strong>
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

      {recommendation && (
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>Recommendation</strong>
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
          <p style={{ color: "var(--muted)" }}>{recommendation.deadline_note}</p>
        </div>
      )}

      {report && (
        <div className="panel">
          <strong>Full report</strong>
          <pre className="report">{report}</pre>
        </div>
      )}

      {phase === "error" && <p className="error">Error: {error}</p>}
    </main>
  );
}
