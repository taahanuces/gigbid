import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  getPublicTrace,
  publicTraceDisclosure,
  publicTraces,
} from "@/lib/public-traces";

export function generateStaticParams() {
  return publicTraces.map((trace) => ({ slug: trace.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const trace = getPublicTrace(slug);
  return trace
    ? { title: `${trace.title} | GigBid trace`, description: trace.summary }
    : { title: "Trace not found | GigBid" };
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export default async function PublicTracePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const trace = getPublicTrace(slug);
  if (!trace) notFound();

  return (
    <main className="public-trace-page">
      <header className="public-trace-hero compact">
        <div className="public-trace-topline">
          <Link className="public-trace-brand" href="/traces">GigBid traces</Link>
          <span className="public-trace-label">Synthetic · redacted · read-only</span>
        </div>
        <h1>{trace.title}</h1>
        <p>{trace.summary}</p>
        <div className="public-trace-id"><span>Trace ID</span><code>{trace.trace_id}</code></div>
      </header>

      <section className="public-trace-metrics" aria-label="Trace metrics">
        {Object.entries(trace.metrics).map(([label, value]) => (
          <article key={label}>
            <span>{label.replaceAll("_", " ")}</span>
            <strong>{formatValue(value)}</strong>
          </article>
        ))}
      </section>

      <section className="public-trace-panel">
        <div className="section-heading">
          <div><span className="eyebrow">Execution</span><h2>Span timeline</h2></div>
          <span className="badge neutral">{trace.spans.length} spans</span>
        </div>
        <ol className="public-span-list">
          {trace.spans.map((span) => (
            <li key={`${span.sequence}-${span.node}`}>
              <span className="public-span-sequence">{String(span.sequence).padStart(2, "0")}</span>
              <div>
                <strong>{span.node.replaceAll("_", " ")}</strong>
                <small>{span.status.replaceAll("_", " ")}</small>
                {Object.keys(span.attributes).length ? (
                  <dl>
                    {Object.entries(span.attributes).map(([key, value]) => (
                      <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{formatValue(value)}</dd></div>
                    ))}
                  </dl>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <div className="public-trace-columns">
        <section className="public-trace-panel">
          <span className="eyebrow">Verified invariants</span>
          <h2>Assertions</h2>
          <ul>{trace.assertions.map((assertion) => <li key={assertion}>{assertion}</li>)}</ul>
        </section>
        <section className="public-trace-panel">
          <span className="eyebrow">Reproduction</span>
          <h2>Evidence references</h2>
          <ul className="public-code-list">
            {trace.evidence_refs.map((reference) => <li key={reference}><code>{reference}</code></li>)}
          </ul>
        </section>
      </div>

      <details className="public-trace-panel public-trace-raw">
        <summary>Inspect redacted terminal state</summary>
        <pre>{JSON.stringify(trace.redacted_state, null, 2)}</pre>
      </details>

      <footer className="public-trace-footer">
        <p>{publicTraceDisclosure}</p>
        <Link className="text-link" href="/traces">View all public traces</Link>
      </footer>
    </main>
  );
}
