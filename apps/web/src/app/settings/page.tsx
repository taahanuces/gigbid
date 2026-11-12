"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { ProfileForm } from "@/components/ProfileForm";
import { PortfolioManager } from "@/components/PortfolioManager";
import { api, type MemoryItem, type Profile, type ProfileSettings } from "@/lib/api/client";

export default function SettingsPage() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<ProfileSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([api.memories(), api.profile()])
      .then(([items, loadedProfile]) => {
        if (active) {
          setMemories(items);
          setProfile(loadedProfile);
          setSettings(loadedProfile.settings);
        }
      })
      .catch((caught: Error) => {
        if (active) setError(caught.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function forget(memory: MemoryItem) {
    setError("");
    try {
      await api.deleteMemory(memory);
      setMemories((items) => items.filter((item) => item.key !== memory.key));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete memory");
    }
  }

  async function saveSettings() {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const updated = await api.saveProfile({ ...settings, approval_required: true });
      setProfile(updated);
      setSettings(updated.settings);
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Control center"
        title="Settings"
        description="Configure marketplace mode, budgets, searches, autonomy, and inspect promoted memories."
      />
      <div className="settings-grid">
        <section className="section-card">
          <span className="eyebrow">Marketplace</span>
          <h2>GigSim</h2>
          <p>Development and grading adapter is active.</p>
          <span className="badge success">{profile?.marketplace_mode ?? "loading"}</span>
        </section>
        <section className="section-card">
          <span className="eyebrow">Autonomy</span>
          <h2>Approval required</h2>
          <p>Low-fit jobs may be auto-skipped. Proposals and messages can never auto-send.</p>
          <span className="badge success">Enforced</span>
        </section>
        <section className="section-card span-two profile-card">
          <div className="section-heading">
            <div><span className="eyebrow">Bid profile</span><h2>Portfolio and boundaries</h2></div>
            {profile ? <span className="badge neutral">{profile.evidence_count} evidence records</span> : null}
          </div>
          {saved ? <p className="notice-message">Settings saved. New runs will use this portfolio and fixed-price floor.</p> : null}
          {settings ? <><ProfileForm settings={settings} onChange={setSettings} onSubmit={saveSettings} busy={saving} submitLabel="Save settings" /><PortfolioManager persona={settings.persona ?? "data-analyst"} /></> : <p>Loading settings…</p>}
        </section>
        <section className="section-card span-two">
          <span className="eyebrow">Long-term memory</span>
          <h2>
            {memories.length ? `${memories.length} promoted memories` : "No promoted memories yet"}
          </h2>
          <p>
            Style patterns need three consistent approved edits; outcome strategies need at least five
            observations. You can inspect and delete every promoted memory.
          </p>
          {error ? <div className="error-message">{error}</div> : null}
          {loading ? <p>Loading memory…</p> : null}
          {!loading && memories.length ? (
            <div className="memory-list">
              {memories.map((memory) => (
                <article className="memory-row" key={memory.key}>
                  <div>
                    <span
                      className={`badge ${memory.kind === "style" ? "success" : "neutral"}`}
                    >
                      {memory.kind}
                    </span>
                    <strong>{memory.value.replaceAll("_", " ")}</strong>
                    <small>
                      {memory.evidence_count} supporting observations
                      {memory.category ? ` · ${memory.category}` : ""}
                    </small>
                  </div>
                  <button
                    aria-label={`Forget ${memory.value}`}
                    className="button danger-button"
                    onClick={() => forget(memory)}
                  >
                    Forget
                  </button>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
