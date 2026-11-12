"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { api, type Pipeline } from "@/lib/api/client";

const columns = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"] as const;

export default function PipelinePage() {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.pipeline().then(setPipeline).catch((caught: Error) => setError(caught.message)); }, []);

  return (
    <AppShell>
      <PageHeader eyebrow="Outcome tracking" title="Pipeline" description="Draft and simulator outcome events move cards; only observed outcomes can enter memory." />
      {error ? <p className="error-message">{error}</p> : null}
      <div className="kanban">
        {columns.map((column) => {
          const cards = pipeline?.cards.filter((card) => card.status === column) ?? [];
          return <section key={column}><header><strong>{column}</strong><span>{cards.length}</span></header>{cards.map((card) => <Link href={`/jobs/${card.job_id}`} key={card.proposal_id}><article><small>{card.connects_spent} Connects · {card.data_origin.replaceAll("_", " ")}</small><h3>{card.title}</h3><p>{card.status}</p></article></Link>)}{cards.length === 0 ? <div className="kanban-empty">No jobs</div> : null}</section>;
        })}
      </div>
    </AppShell>
  );
}

