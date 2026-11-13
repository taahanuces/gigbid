import traceDataset from "@/data/public-traces.json";

export type PublicTraceSpan = {
  sequence: number;
  node: string;
  status: string;
  attributes: Record<string, unknown>;
};

export type PublicTrace = {
  slug: string;
  trace_id: string;
  title: string;
  status: string;
  summary: string;
  data_origin: string;
  metrics: Record<string, string | number | boolean>;
  assertions: string[];
  evidence_refs: string[];
  spans: PublicTraceSpan[];
  redacted_state: Record<string, unknown>;
};

type PublicTraceDataset = {
  generated_at: string;
  schema_version: number;
  disclosure: string;
  traces: PublicTrace[];
};

const dataset = traceDataset as unknown as PublicTraceDataset;

export const publicTraces = dataset.traces;
export const publicTraceDisclosure = dataset.disclosure;
export const publicTraceGeneratedAt = dataset.generated_at;

export function getPublicTrace(slug: string): PublicTrace | undefined {
  return publicTraces.find((trace) => trace.slug === slug);
}
