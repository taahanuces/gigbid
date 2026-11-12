"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import {
  api,
  type CheckpointHistory,
  type CheckpointReplay,
  type RunState,
  type RunNodeEvent,
} from "@/lib/api/client";

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<RunState | null>(null);
  const [history, setHistory] = useState<CheckpointHistory | null>(null);
  const [replay, setReplay] = useState<CheckpointReplay | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.run(id), api.runHistory(id)])
      .then(([currentRun, checkpoints]) => {
        setRun(currentRun);
        setHistory(checkpoints);
      })
      .catch((caught: Error) => setError(caught.message));
    api.streamRunEvents(
      id,
      {
        onNode: (event) => {
          setRun((current) => {
            if (!current) return current;
            const existing = (current.state.events as RunNodeEvent[] | undefined) ?? [];
            const key = JSON.stringify(event);
            if (existing.some((item) => JSON.stringify(item) === key)) return current;
            return { ...current, state: { ...current.state, events: [...existing, event] } };
          });
        },
        onStatus: (status) => {
          setRun((current) => current ? { ...current, status } : current);
          Promise.all([api.run(id), api.runHistory(id)])
            .then(([currentRun, checkpoints]) => {
              setRun(currentRun);
              setHistory(checkpoints);
            })
            .catch(() => undefined);
        },
      },
      controller.signal,
    ).catch((caught: Error) => {
      if (caught.name !== "AbortError") setError((current) => current || caught.message);
    });
    return () => controller.abort();
  }, [id]);

  async function inspectCheckpoint(checkpointId: string) {
    setBusy(true);
    try {
      setReplay(await api.replayCheckpoint(id, checkpointId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Checkpoint replay failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      setRun(await api.approval(id, { action: "approve" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!rejectReason.trim()) {
      setError("A rejection reason is required.");
      return;
    }
    setBusy(true);
    try {
      setRun(await api.approval(id, { action: "reject", reason: rejectReason.trim() }));
      setShowReject(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Rejection failed");
    } finally {
      setBusy(false);
    }
  }

  const state = replay?.state ?? run?.state ?? {};
  const events = (state.events as RunNodeEvent[] | undefined) ?? [];
  const approval = state.approval_payload as Record<string, any> | undefined;
  const displayedStatus = replay?.status ?? run?.status;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Live execution"
        title="Agent run"
        description={`Thread ${id.slice(0, 8)} · ${displayedStatus ?? "loading"}`}
        actions={<Link className="button secondary" href={`/studio/${id}`}>Open proposal studio</Link>}
      />
      {error ? <p className="error-message">{error}</p> : null}
      {replay ? (
        <p className="notice-message">
          Read-only checkpoint replay · {replay.checkpoint_id.slice(0, 12)}
          <button className="button secondary compact-button" onClick={() => setReplay(null)}>Return to live state</button>
        </p>
      ) : null}
      {run?.trace_id ? (
        <div className="trace-strip" aria-label="Trace details">
          <span><strong>Trace</strong> <code>{run.trace_id}</code></span>
          {run.trace_url ? <a className="text-link" href={run.trace_url} target="_blank" rel="noreferrer">Open trace viewer</a> : <small>Correlates API, graph, and audit events.</small>}
        </div>
      ) : null}
      <div className="run-layout">
        <section className="section-card">
          <div className="section-heading"><div><span className="eyebrow">Timeline</span><h2>Node progress</h2></div><span className="badge neutral">{events.length} events</span></div>
          <ol className="timeline">
            {events.map((event, index) => (
              <li key={`${event.node}-${index}`}>
                <span className="timeline-dot" />
                <div><strong>{event.node?.replaceAll("_", " ")}</strong><small>{String(event.action ?? event.status ?? (event.passed ? "passed" : "complete"))}</small></div>
              </li>
            ))}
          </ol>
        </section>
        <aside className="section-card approval-card">
          <span className="eyebrow">Human gate</span>
          <h2>{displayedStatus === "awaiting_approval" ? "Review required" : "Run status"}</h2>
          {approval ? (
            <>
              <div className="approval-cost"><span>Connects cost</span><strong>{approval.dry_run?.connects_cost ?? 0}</strong></div>
              <p>{approval.risk_report?.explanation}</p>
              <div className="approval-actions">
                <button className="button primary" disabled={busy || Boolean(replay) || run?.status !== "awaiting_approval"} onClick={approve}>Approve draft</button>
                <button className="button danger-button" disabled={busy || Boolean(replay) || run?.status !== "awaiting_approval"} onClick={() => setShowReject(true)}>Reject</button>
              </div>
              {showReject ? (
                <div className="reject-panel">
                  <label htmlFor="rejection-reason">Reason for rejection</label>
                  <textarea id="rejection-reason" value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} />
                  <button className="button danger-button" disabled={busy} onClick={reject}>Confirm rejection</button>
                </div>
              ) : null}
              <small>Approval creates a marketplace draft only. No automatic final submission.</small>
            </>
          ) : <p>{displayedStatus ?? "Loading checkpoint…"}</p>}
        </aside>
      </div>
      <section className="section-card checkpoint-card">
        <div className="section-heading">
          <div><span className="eyebrow">Durable history</span><h2>Checkpoint replay</h2></div>
          <span className="badge neutral">{history?.checkpoints.length ?? 0} checkpoints</span>
        </div>
        <p>Inspect a prior state without rerunning nodes or repeating marketplace writes.</p>
        <div className="checkpoint-list">
          {history?.checkpoints.slice(0, 12).map((checkpoint) => (
            <button
              className="checkpoint-button"
              disabled={busy}
              key={checkpoint.checkpoint_id}
              onClick={() => inspectCheckpoint(checkpoint.checkpoint_id)}
            >
              <strong>{checkpoint.status.replaceAll("_", " ")}</strong>
              <small>Step {checkpoint.step_count ?? 0} · {checkpoint.next_nodes?.join(", ") || "complete"}</small>
            </button>
          ))}
        </div>
      </section>
    </AppShell>
  );
}

