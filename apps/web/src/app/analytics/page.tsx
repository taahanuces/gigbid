"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { api, type Analytics } from "@/lib/api/client";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.analytics().then(setAnalytics).catch((caught: Error) => setError(caught.message));
  }, []);

  const summary = useMemo(() => {
    const personas = Object.values(analytics?.personas ?? {});
    const average = (field: "reply_rate" | "hire_rate") => personas.length
      ? personas.reduce((total, item) => total + item[field], 0) / personas.length
      : 0;
    return {
      reply: average("reply_rate"),
      hire: average("hire_rate"),
      p95: personas.length ? Math.max(...personas.map((item) => item.p95_latency_seconds)) : 0,
      unsupported: analytics?.rag_variants.v2_hybrid?.unsupported_claims_after ?? 0,
      cost: personas.reduce((total, item) => total + (item.model_cost_usd ?? 0), 0),
    };
  }, [analytics]);

  return (
    <AppShell>
      <PageHeader eyebrow="Measured outcomes" title="Analytics" description="Every value is loaded from a committed evaluation result, with synthetic scope shown explicitly." />
      {error ? <p className="error-message">{error}</p> : null}
      <section className="metrics-grid">
        <MetricCard label="Reply rate" value={analytics ? percent(summary.reply) : "—"} detail="Deterministic simulator average" />
        <MetricCard label="Hire rate" value={analytics ? percent(summary.hire) : "—"} detail="Deterministic simulator average" />
        <MetricCard label="p95 proposal" value={analytics ? `${(summary.p95 * 1000).toFixed(1)} ms` : "—"} detail="Local deterministic graph" />
        <MetricCard label="Unsupported claims" value={analytics ? String(summary.unsupported) : "—"} detail="After verification, V2" />
        <MetricCard label="Connects used" value={analytics ? String(analytics.connects_spent ?? 0) : "—"} detail="Fixed synthetic outcome study" />
        <MetricCard label="Model cost" value={analytics ? `$${summary.cost.toFixed(2)}` : "—"} detail="Local deterministic run" />
      </section>
      <section className="section-card">
        <div className="section-heading"><div><span className="eyebrow">Outcome study</span><h2>By persona</h2></div><span className="badge neutral">Synthetic</span></div>
        <p>{analytics?.scope ?? "Loading evaluation scope…"}</p>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead><tr><th>Persona</th><th>Bid F1</th><th>Scam P/R</th><th>Reply</th><th>Hire</th><th>p95</th></tr></thead>
            <tbody>{Object.entries(analytics?.personas ?? {}).map(([name, row]) => (
              <tr key={name}><td>{name.replaceAll("-", " ")}</td><td>{percent(row.bid_or_skip_f1)}</td><td>{percent(row.scam_precision)} / {percent(row.scam_recall)}</td><td>{percent(row.reply_rate)}</td><td>{percent(row.hire_rate)}</td><td>{(row.p95_latency_seconds * 1000).toFixed(1)} ms</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
      <section className="section-card checkpoint-card">
        <div className="section-heading"><div><span className="eyebrow">Retrieval study</span><h2>RAG variants</h2></div><span className="badge neutral">90 jobs</span></div>
        <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Variant</th><th>Recall@5</th><th>nDCG@10</th><th>Unsupported</th><th>p95</th></tr></thead><tbody>{Object.entries(analytics?.rag_variants ?? {}).map(([name, row]) => <tr key={name}><td>{name}</td><td>{row.evidence_recall_at_5.toFixed(3)}</td><td>{row.ndcg_at_10.toFixed(3)}</td><td>{row.unsupported_claims_after}</td><td>{row.p95_latency_ms.toFixed(1)} ms</td></tr>)}</tbody></table></div>
      </section>
      <section className="section-card checkpoint-card">
        <div className="section-heading"><div><span className="eyebrow">Outcome study</span><h2>By job category</h2></div><span className="badge neutral">Synthetic</span></div>
        <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Category</th><th>Proposals</th><th>Reply</th><th>Hire</th><th>Connects</th></tr></thead><tbody>{Object.entries(analytics?.categories ?? {}).slice(0, 12).map(([name, row]) => <tr key={name}><td>{name}</td><td>{row.proposals}</td><td>{percent(row.reply_rate)}</td><td>{percent(row.hire_rate)}</td><td>{row.connects_spent}</td></tr>)}</tbody></table></div>
      </section>
      <section className="section-card checkpoint-card">
        <div className="section-heading"><div><span className="eyebrow">Safety decisions</span><h2>Top rejection reasons</h2></div></div>
        <div className="tag-row large">{Object.entries(analytics?.top_rejection_reasons ?? {}).map(([reason, count]) => <span key={reason}>{reason.replaceAll("_", " ")} · {count}</span>)}</div>
      </section>
    </AppShell>
  );
}

