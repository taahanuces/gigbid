"use client";

import type { FormEvent } from "react";

import type { ProfileSettings } from "@/lib/api/client";

type Props = {
  settings: ProfileSettings;
  busy: boolean;
  submitLabel: string;
  onChange: (settings: ProfileSettings) => void;
  onSubmit: () => void;
};

export function ProfileForm({ settings, busy, submitLabel, onChange, onSubmit }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  function number(name: keyof ProfileSettings, value: string) {
    onChange({ ...settings, [name]: Number(value) });
  }

  return (
    <form className="profile-form" onSubmit={submit}>
      <label className="span-two">
        Portfolio persona
        <select
          value={settings.persona}
          onChange={(event) => onChange({ ...settings, persona: event.target.value as ProfileSettings["persona"] })}
        >
          <option value="data-analyst">Data analyst</option>
          <option value="full-stack-developer">Full-stack developer</option>
          <option value="ai-ml-engineer">AI / ML engineer</option>
        </select>
        <small>Changes which clearly synthetic portfolio index grounds proposals.</small>
      </label>
      <label>
        Hourly rate (USD)
        <input type="number" min="0" step="1" value={settings.hourly_rate} onChange={(event) => number("hourly_rate", event.target.value)} />
      </label>
      <label>
        Fixed-price floor (USD)
        <input type="number" min="0" step="25" value={settings.fixed_price_floor} onChange={(event) => number("fixed_price_floor", event.target.value)} />
      </label>
      <label>
        Weekly Connects budget
        <input type="number" min="0" step="1" value={settings.weekly_connects_budget} onChange={(event) => number("weekly_connects_budget", event.target.value)} />
      </label>
      <label>
        Max Connects per bid
        <input type="number" min="0" max="100" step="1" value={settings.max_connects_per_bid} onChange={(event) => number("max_connects_per_bid", event.target.value)} />
      </label>
      <label className="span-two">
        Search keywords
        <input
          value={(settings.search_keywords ?? []).join(", ")}
          onChange={(event) => onChange({
            ...settings,
            search_keywords: event.target.value.split(",").map((item) => item.trim()),
          })}
          placeholder="python, analytics, automation"
        />
      </label>
      <div className="profile-policy span-two">
        <strong>Human approval is permanently required</strong>
        <small>GigBid can auto-skip weak jobs, but proposals and messages cannot auto-send.</small>
      </div>
      <button className="button primary span-two" disabled={busy} type="submit">
        {busy ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
