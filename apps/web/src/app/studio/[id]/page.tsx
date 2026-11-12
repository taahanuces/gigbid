"use client";

import { use, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { api, type RunState } from "@/lib/api/client";

export default function StudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<RunState | null>(null);
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState("");
  const [paragraphIndex, setParagraphIndex] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.run(id).then((value) => {
      setRun(value);
      const proposal = value.state.proposal_draft as { cover_letter?: string } | undefined;
      setDraft(proposal?.cover_letter ?? "");
    }).catch((error: Error) => setMessage(error.message));
  }, [id]);

  async function saveEdit() {
    setBusy(true);
    try {
      const result = await api.approval(id, { action: "edit", edited_cover_letter: draft });
      setRun(result);
      setMessage("Edit saved and sent back through compliance.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Edit failed");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    setBusy(true);
    try {
      const result = await api.regenerateParagraph(id, paragraphIndex);
      const paragraphs = draft.split("\n\n");
      paragraphs[result.paragraph_index] = result.replacement;
      setDraft(paragraphs.join("\n\n"));
      setMessage(`Paragraph regenerated: ${result.reasons.join(", ").replaceAll("_", " ")}. Save the edit to rerun verification.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Paragraph regeneration failed");
    } finally {
      setBusy(false);
    }
  }

  const evidence = (run?.state.evidence as Array<{ evidence_id: string; title: string; text: string }> | undefined) ?? [];
  const critique = run?.state.critique as { passed?: boolean; grounding_score?: number; personalization_score?: number; revision_instructions?: string[] } | undefined;
  const compliance = run?.state.compliance_verdict as { passed?: boolean; blocked_rule_ids?: string[]; comments?: string[] } | undefined;
  const approval = run?.state.approval_payload as { dry_run?: { tool_name?: string; connects_cost?: number; side_effects?: string[] } } | undefined;
  const paragraphCount = Math.max(1, draft.split("\n\n").length);
  return (
    <AppShell>
      <PageHeader eyebrow="Proposal studio" title="Grounded draft" description="Every experience claim is tied to portfolio evidence before approval." />
      {message ? <p className="notice-message">{message}</p> : null}
      <div className="studio-layout">
        <section className="section-card editor-card">
          <div className="section-heading"><div><span className="eyebrow">Draft editor</span><h2>Cover letter</h2></div><span className="badge success">Claims verified</span></div>
          {critique ? (
            <div className="critic-strip">
              <div><span>Grounding</span><strong>{Math.round((critique.grounding_score ?? 0) * 100)}%</strong></div>
              <div><span>Personalization</span><strong>{Math.round((critique.personalization_score ?? 0) * 100)}%</strong></div>
              <p>{critique.revision_instructions?.join(" ") || "Critic checks passed."}</p>
            </div>
          ) : null}
          <textarea aria-label="Proposal cover letter" value={draft} onChange={(event) => setDraft(event.target.value)} />
          <div className="citation-strip" aria-label="Cited evidence">
            {evidence.map((item) => <abbr key={item.evidence_id} title={item.text}>[{item.evidence_id}]</abbr>)}
          </div>
          <div className="editor-footer"><span>{draft.split(/\s+/).filter(Boolean).length} words</span><div><label className="paragraph-picker">Paragraph <select aria-label="Paragraph to regenerate" value={paragraphIndex} onChange={(event) => setParagraphIndex(Number(event.target.value))}>{Array.from({ length: paragraphCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><button className="button secondary" disabled={busy} onClick={regenerate}>Regenerate paragraph</button><button className="button primary" disabled={busy} onClick={saveEdit}>Save edit</button></div></div>
        </section>
        <aside className="section-card evidence-panel">
          <span className="eyebrow">Evidence</span>
          <h2>Claim sources</h2>
          {evidence.map((item) => <article key={item.evidence_id}><span>{item.evidence_id}</span><strong>{item.title}</strong><p>{item.text}</p></article>)}
          <article>
            <span>Compliance review</span>
            <strong>{compliance?.passed ? "Passed" : compliance ? "Blocked" : "Pending"}</strong>
            <p>{compliance?.comments?.join(" ") || "No compliance comments."}</p>
            {compliance?.blocked_rule_ids?.length ? <small>Rules: {compliance.blocked_rule_ids.join(", ")}</small> : null}
          </article>
          <article>
            <span>Dry-run preview</span>
            <strong>{approval?.dry_run?.tool_name?.replaceAll("_", " ") ?? "Marketplace draft"}</strong>
            <p>{approval?.dry_run?.connects_cost ?? 0} Connects · nothing is sent until approval.</p>
            {approval?.dry_run?.side_effects?.length ? <small>{approval.dry_run.side_effects.join(" · ")}</small> : null}
          </article>
        </aside>
      </div>
    </AppShell>
  );
}

