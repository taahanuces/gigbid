"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { api, type InboxJob, type Pipeline, type Profile } from "@/lib/api/client";

export default function InboxPage() {
  const [jobs, setJobs] = useState<InboxJob[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [filter, setFilter] = useState<"all" | "bid" | "skip">("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [rankedJobs, loadedProfile, loadedPipeline] = await Promise.all([
        api.inbox(), api.profile(), api.pipeline(),
      ]);
      setJobs(rankedJobs);
      setProfile(loadedProfile);
      setPipeline(loadedPipeline);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const visibleJobs = jobs.filter((job) => filter === "all" || job.action === filter);
  const recommended = jobs.filter((job) => job.action === "bid").length;
  const risks = jobs.filter((job) => (job.risk_score ?? 0) >= 0.7).length;
  const connectsSpent = pipeline?.cards.reduce((sum, card) => sum + (card.connects_spent ?? 0), 0) ?? 0;
  const connectsBudget = profile?.settings.weekly_connects_budget ?? 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Opportunity desk"
        title="Job inbox"
        description="New work, ranked by evidence fit and risk before you spend a single Connect."
        actions={<button className="button secondary" disabled={loading} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh ranked inbox"}</button>}
      />
      <section className="metrics-grid" aria-label="Inbox summary">
        <MetricCard label="New jobs" value={String(jobs.length)} detail="Since the last scout run" />
        <MetricCard label="Recommended" value={String(recommended)} detail="Measured evidence coverage" />
        <MetricCard label="Risk caught" value={String(risks)} detail="At or above the risk threshold" />
        <MetricCard label="Weekly budget" value={`${connectsSpent} / ${connectsBudget}`} detail="Connects spent versus limit" />
      </section>
      <section className="section-card">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Ranked queue</span>
            <h2>Review opportunities</h2>
          </div>
          <div className="filter-row">
            <button className={`chip ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>All</button>
            <button className={`chip ${filter === "bid" ? "active" : ""}`} onClick={() => setFilter("bid")}>Recommended</button>
            <button className={`chip ${filter === "skip" ? "active" : ""}`} onClick={() => setFilter("skip")}>Skipped</button>
          </div>
        </div>
        {error ? (
          <div className="empty-state">
            <strong>Marketplace unavailable</strong>
            <p>{error}. Work is queued and will resume when the service recovers.</p>
            <Link className="button secondary" href="/login">Sign in</Link>
          </div>
        ) : loading && jobs.length === 0 ? (
          <div className="empty-state"><p>Loading marketplace jobs…</p></div>
        ) : visibleJobs.length === 0 ? (
          <div className="empty-state"><p>No jobs match this filter.</p></div>
        ) : (
          <div className="job-list">
            {visibleJobs.map((job, index) => (
              <Link className="job-row" href={`/jobs/${job.job_id}`} key={job.job_id}>
                <div className="job-rank">{String(index + 1).padStart(2, "0")}</div>
                <div className="job-main">
                  <div className="job-title-row">
                    <h3>{job.title}</h3>
                    <span className={`badge ${job.action === "bid" ? "success" : job.action === "skip" ? "danger" : "neutral"}`}>
                      {job.action}
                    </span>
                  </div>
                  <p>{job.description}</p>
                  <div className="tag-row">
                    {job.required_skills.slice(0, 4).map((skill) => <span key={skill}>{skill}</span>)}
                  </div>
                </div>
                <div className="job-meta">
                  <strong>{job.budget.min ?? "Open"}–{job.budget.max ?? "Open"} {job.budget.currency}</strong>
                  <span>{job.connects_cost} Connects</span>
                  <small>{job.fit_score == null ? "Analysis pending" : `${Math.round(job.fit_score * 100)}% fit · ${Math.round((job.risk_score ?? 0) * 100)}% risk`}</small>
                  {job.recommended_price != null ? <small>{job.recommended_price.toFixed(0)} USD recommended</small> : null}
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}

