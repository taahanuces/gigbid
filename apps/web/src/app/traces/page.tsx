import type { Metadata } from "next";
import Link from "next/link";

import {
  publicTraceDisclosure,
  publicTraceGeneratedAt,
  publicTraces,
} from "@/lib/public-traces";

export const metadata: Metadata = {
  title: "Public execution traces | GigBid",
  description: "Read-only, redacted GigSim execution traces for the GigBid assignment.",
};

export default function PublicTracesPage() {
  return (
    <main className="public-trace-page">
      <header className="public-trace-hero">
        <Link className="public-trace-brand" href="/">GigBid</Link>
        <span className="public-trace-label">Public evidence</span>
        <h1>Read-only agent traces</h1>
        <p>{publicTraceDisclosure}</p>
        <small>Generated {new Date(publicTraceGeneratedAt).toLocaleString("en-GB", { timeZone: "UTC" })} UTC</small>
      </header>
      <section className="public-trace-index" aria-label="Available traces">
        {publicTraces.map((trace) => (
          <Link className="public-trace-card" href={`/traces/${trace.slug}`} key={trace.slug}>
            <span className="badge success">{trace.status.replaceAll("_", " ")}</span>
            <h2>{trace.title}</h2>
            <p>{trace.summary}</p>
            <code>{trace.trace_id}</code>
          </Link>
        ))}
      </section>
    </main>
  );
}
