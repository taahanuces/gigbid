"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { ProfileForm } from "@/components/ProfileForm";
import { PortfolioManager } from "@/components/PortfolioManager";
import { api, type Profile, type ProfileSettings } from "@/lib/api/client";

export default function OnboardingPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<ProfileSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.profile()
      .then((result) => {
        setProfile(result);
        setSettings(result.settings);
      })
      .catch((caught: Error) => setError(caught.message));
  }, []);

  async function complete() {
    if (!settings) return;
    setBusy(true);
    setError("");
    try {
      await api.saveProfile({ ...settings, onboarding_complete: true, approval_required: true });
      router.push("/inbox");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save profile");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Profile setup"
        title="Onboarding"
        description="Choose the portfolio used for evidence retrieval and set firm bidding boundaries. All choices persist in the durable profile store."
      />
      {error ? <p className="error-message">{error}</p> : null}
      {profile ? (
        <div className="metrics-grid onboarding-metrics">
          <article className="metric-card"><span>Marketplace</span><strong>{profile.marketplace_mode}</strong><small>Approved local adapter</small></article>
          <article className="metric-card"><span>Portfolio records</span><strong>{profile.evidence_count}</strong><small>Clearly synthetic evidence</small></article>
          <article className="metric-card"><span>External sends</span><strong>0 auto</strong><small>Approval invariant</small></article>
          <article className="metric-card"><span>Data boundary</span><strong>Mixed</strong><small>Public jobs + synthetic profile</small></article>
        </div>
      ) : null}
      <section className="section-card profile-card">
        <div className="section-heading"><div><span className="eyebrow">Your operating policy</span><h2>Configure GigBid</h2></div></div>
        {settings ? (
          <><ProfileForm settings={settings} onChange={setSettings} onSubmit={complete} busy={busy} submitLabel="Save and open job inbox" /><PortfolioManager persona={settings.persona ?? "data-analyst"} /></>
        ) : <p>Loading profile…</p>}
      </section>
    </AppShell>
  );
}

