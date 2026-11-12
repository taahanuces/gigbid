"use client";

import { useEffect, useState } from "react";

import { api, type PortfolioEvidence } from "@/lib/api/client";

export function PortfolioManager({ persona }: { persona: string }) {
  const [items, setItems] = useState<PortfolioEvidence[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [skills, setSkills] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.portfolio().then(setItems).catch((error: Error) => setMessage(error.message));
  }, []);

  async function upload() {
    if (!file) {
      setMessage("Choose a PDF, Markdown, or text portfolio file.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const created = await api.uploadPortfolio(file, persona, skills);
      setItems((current) => [
        ...current.filter((item) => !created.some((added) => added.evidence_id === item.evidence_id)),
        ...created,
      ]);
      setFile(null);
      setMessage(`${created.length} evidence chunk${created.length === 1 ? "" : "s"} indexed.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: PortfolioEvidence) {
    await api.deletePortfolio(item.evidence_id);
    setItems((current) => current.filter((record) => record.evidence_id !== item.evidence_id));
  }

  return (
    <div className="portfolio-manager">
      <div>
        <span className="eyebrow">Private portfolio</span>
        <h3>Incremental evidence index</h3>
        <p>PDF, Markdown and text uploads stay in your tenant-scoped store and join the selected persona index.</p>
      </div>
      <div className="portfolio-upload-row">
        <label>Portfolio file<input aria-label="Portfolio file" accept=".pdf,.md,.markdown,.txt" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <label>Skills, comma separated<input aria-label="Portfolio skills" value={skills} onChange={(event) => setSkills(event.target.value)} placeholder="Python, FastAPI, PostgreSQL" /></label>
        <button className="button secondary" disabled={busy} type="button" onClick={upload}>{busy ? "Indexing…" : "Upload and index"}</button>
      </div>
      {message ? <p className="form-note">{message}</p> : null}
      {items.length ? (
        <div className="portfolio-list">
          {items.map((item) => (
            <article key={item.evidence_id}>
              <div><strong>{item.title}</strong><small>{item.type.replaceAll("_", " ")} · {(item.skills ?? []).join(", ") || "No skills tagged"}</small></div>
              <button aria-label={`Delete ${item.title}`} className="button danger-button" type="button" onClick={() => remove(item)}>Delete</button>
            </article>
          ))}
        </div>
      ) : <small>No private uploads indexed yet.</small>}
    </div>
  );
}
