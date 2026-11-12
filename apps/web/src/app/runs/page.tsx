import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";

export default function RunsPage() {
  return (
    <AppShell>
      <PageHeader eyebrow="Observability" title="Agent runs" description="Inspect every node, tool call, decision, and approval checkpoint." />
      <section className="section-card empty-state">
        <strong>Choose a job to start a run</strong>
        <p>Active and historical runs will appear here with links to their complete traces.</p>
      </section>
    </AppShell>
  );
}

