"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("reviewer@gigbid.local");
  const [password, setPassword] = useState("GigBidDemo2026!");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      router.push("/inbox");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <span className="eyebrow light">Human-controlled automation</span>
        <h1>Bid with evidence, not instinct.</h1>
        <p>
          GigBid finds strong opportunities, checks every claim, and waits for you before anything
          leaves the system.
        </p>
        <div className="trust-list">
          <span>Grounded proposals</span>
          <span>Scam and injection defense</span>
          <span>Approval before every send</span>
        </div>
      </section>
      <section className="login-panel" aria-labelledby="login-heading">
        <div className="brand login-brand">
          <span className="brand-mark">G</span>
          <strong>GigBid</strong>
        </div>
        <span className="eyebrow">Reviewer access</span>
        <h2 id="login-heading">Welcome back</h2>
        <p>Use the preloaded demo persona to review the complete workflow.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
          </label>
          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
            />
          </label>
          {error ? <p className="error-message">{error}</p> : null}
          <button className="button primary" disabled={busy} type="submit">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <small className="form-note">External actions remain locked until explicit approval.</small>
      </section>
    </main>
  );
}

