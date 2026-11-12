"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { api, type Job, type RunState } from "@/lib/api/client";

type RequirementEvidence = {
  requirement: string;
  evidence_ids: string[];
  supported: boolean;
  explanation: string;
};

type FitReport = {
  score?: number;
  explanation?: string;
  requirement_matrix?: RequirementEvidence[];
};

type RiskReport = { score?: number; flags?: string[]; explanation?: string };
type BidDecision = { action?: string; confidence?: number; reasons?: string[] };
type PriceQuote = {
  amount?: number;
  currency?: string;
  fair_band_min?: number;
  fair_band_max?: number;
  floor_amount?: number;
  rationale?: string;
  market_prior_category?: string;
  market_prior_sample_size?: number;
};
type Evidence = { evidence_id: string; title: string };

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [analysis, setAnalysis] = useState<RunState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api.job(id)
      .then((loadedJob) => {
        if (active) setJob(loadedJob);
        return api.inbox();
      })
      .then((items) => items.find((item) => item.job_id === id)?.thread_id)
      .then((threadId) => threadId ? api.run(threadId) : null)
      .then((run) => {
        if (active && run) setAnalysis(run);
      })
      .catch((caught: Error) => {
        if (active) setError(caught.message);
      });
    return () => { active = false; };
  }, [id]);

  async function analyze() {
    setBusy(true);
    try {
      const run = await api.analyze(id);
      router.push(`/runs/${run.thread_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed");
      setBusy(false);
    }
  }

  const fit = analysis?.state.fit_report as FitReport | undefined;
  const risk = analysis?.state.risk_report as RiskReport | undefined;
  const decision = analysis?.state.decision as BidDecision | undefined;
  const price = analysis?.state.price_quote as PriceQuote | undefined;
  const evidence = (analysis?.state.evidence as Evidence[] | undefined) ?? [];
  const evidenceById = new Map(evidence.map((item) => [item.evidence_id, item]));
  const fitPercent = fit?.score == null ? null : Math.round(fit.score * 100);
  const riskPercent = risk?.score == null ? null : Math.round(risk.score * 100);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Job intelligence"
        title={job?.title ?? "Loading job…"}
        description="Structured requirements, evidence coverage, risk, and price before drafting."
        actions={analysis ? <Link className="button secondary" href={`/runs/${analysis.thread_id}`}>Open agent run</Link> : <button className="button primary" disabled={busy || !job} onClick={analyze}>{busy ? "Agents running…" : "Run analysis"}</button>}
      />
      {error ? <p className="error-message">{error}</p> : null}
      {job ? (
        <div className="detail-grid">
          <section className="section-card span-two">
            <span className="eyebrow">Client brief</span>
            <h2>What the work requires</h2>
            <p className="lead">{job.description}</p>
            <div className="tag-row large">
              {job.required_skills.map((skill) => <span key={skill}>{skill}</span>)}
            </div>
          </section>
          <aside className="section-card decision-card">
            <span className="eyebrow">Decision</span>
            <div className="score-ring"><strong>{fitPercent == null ? "—" : `${fitPercent}%`}</strong><span>evidence fit</span></div>
            <dl>
              <div><dt>Budget</dt><dd>{job.budget.min ?? "Open"}–{job.budget.max ?? "Open"} {job.budget.currency}</dd></div>
              <div><dt>Connects</dt><dd>{job.connects_cost}</dd></div>
              <div><dt>Action</dt><dd>{decision?.action?.replaceAll("_", " ") ?? "Pending"}</dd></div>
              <div><dt>Risk</dt><dd>{riskPercent == null ? "Pending" : `${riskPercent}%`}</dd></div>
              <div><dt>Approval</dt><dd>Required</dd></div>
            </dl>
            {risk?.flags?.length ? <div className="tag-row">{risk.flags.map((flag) => <span key={flag}>{flag.replaceAll("_", " ")}</span>)}</div> : null}
          </aside>
          <section className="section-card span-three">
            <span className="eyebrow">Requirement matrix</span>
            <h2>{fit ? fit.explanation : "Evidence will appear after analysis"}</h2>
            <div className="matrix-placeholder">
              {(fit?.requirement_matrix ?? job.required_skills.map((skill) => ({ requirement: skill, evidence_ids: [], supported: false, explanation: "Waiting for Fit Matcher" }))).map((item) => (
                <div key={item.requirement}>
                  <strong>{item.requirement}</strong>
                  <span>{item.evidence_ids.length ? item.evidence_ids.map((evidenceId) => evidenceById.get(evidenceId)?.title ?? evidenceId).join(" · ") : item.explanation}</span>
                  <span className={`badge ${item.supported ? "success" : "neutral"}`}>{item.supported ? "supported" : "gap"}</span>
                </div>
              ))}
            </div>
          </section>
          {analysis ? (
            <>
              <section className="section-card span-two">
                <span className="eyebrow">Bid reasoning</span>
                <h2>{decision?.action?.replaceAll("_", " ") ?? analysis.status}</h2>
                <p>{risk?.explanation}</p>
                <ul>{decision?.reasons?.map((reason) => <li key={reason}>{reason}</li>)}</ul>
              </section>
              <aside className="section-card">
                <span className="eyebrow">Price rationale</span>
                <h2>{price?.amount == null ? "No quote" : `${price.amount.toFixed(0)} ${price.currency ?? "USD"}`}</h2>
                {price ? <p>Fair band {price.fair_band_min?.toFixed(0)}–{price.fair_band_max?.toFixed(0)} {price.currency ?? "USD"}; floor {price.floor_amount?.toFixed(0)}.</p> : null}
                <p>{price?.rationale ?? "A price is created only for bid candidates."}</p>
                {price?.market_prior_category ? <small>Public prior: {price.market_prior_category} · n={price.market_prior_sample_size ?? 0}</small> : null}
              </aside>
            </>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}

