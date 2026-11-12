import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const baseURL = process.env.GIGBID_DEMO_URL ?? "http://127.0.0.1:3102";
const output = resolve(process.cwd(), "../../docs/assets/demo-frames");
await mkdir(output, { recursive: true });

const jobs = [
  {
    job_id: "job-python-1",
    title: "Analytics API and forecasting dashboard",
    description: "Build a FastAPI analytics service with tested forecasts and a Next.js dashboard.",
    required_skills: ["Python", "FastAPI", "PostgreSQL", "Next.js"],
    budget: { min: 1800, max: 2600, currency: "USD" },
    connects_cost: 8,
    action: "bid",
    fit_score: 0.91,
    risk_score: 0.08,
    recommended_price: 2400,
    reasons: ["Strong verified evidence"],
  },
  {
    job_id: "job-rag-2",
    title: "Grounded RAG support assistant",
    description: "Create an evidence-cited support workflow with retrieval evaluation and monitoring.",
    required_skills: ["RAG", "LangGraph", "Qdrant", "Evaluation"],
    budget: { min: 2200, max: 3200, currency: "USD" },
    connects_cost: 12,
    action: "bid",
    fit_score: 0.87,
    risk_score: 0.12,
    recommended_price: 2950,
    reasons: ["Two verified case studies"],
  },
  {
    job_id: "job-risk-3",
    title: "Urgent automation outside the platform",
    description: "Move payment and communication off-platform before discussing the scope.",
    required_skills: ["Automation", "Python"],
    budget: { min: null, max: null, currency: "USD" },
    connects_cost: 16,
    action: "skip",
    fit_score: 0.62,
    risk_score: 0.94,
    recommended_price: null,
    reasons: ["Off-platform payment request"],
  },
];

const profile = {
  settings: {
    persona: "full-stack-developer",
    hourly_rate: 45,
    fixed_price_floor: 500,
    weekly_connects_budget: 80,
    max_connects_per_bid: 16,
    search_keywords: ["python", "fastapi", "next.js"],
    approval_required: true,
    onboarding_complete: true,
  },
  marketplace_mode: "gigsim",
  evidence_count: 210,
  data_origin: "synthetic persona portfolio; public jobs",
};

const run = {
  thread_id: "run-1",
  status: "awaiting_approval",
  trace_id: "trace-demo-4016",
  trace_url: null,
  state: {
    events: [
      { node: "load_job", status: "complete" },
      { node: "job_analyst", status: "complete" },
      { node: "risk_assessor", status: "complete" },
      { node: "fit_matcher", status: "complete" },
      { node: "pricing", status: "complete" },
      { node: "claim_verifier", passed: true },
      { node: "compliance", passed: true },
    ],
    approval_payload: {
      dry_run: { connects_cost: 8 },
      risk_report: { explanation: "Low-risk client; no policy flags detected." },
    },
    proposal_draft: {
      cover_letter:
        "Your forecasting dashboard maps closely to a verified analytics platform I delivered [case-forecast].\n\nI would build the FastAPI service, tested forecast pipeline, and responsive Next.js views in reviewable milestones [case-api].\n\nBefore implementation, I would confirm the forecast horizon and acceptance metric so the evaluation is explicit.",
    },
    critique: {
      passed: true,
      grounding_score: 1,
      personalization_score: 0.92,
      revision_instructions: [],
    },
    evidence: [
      {
        evidence_id: "case-forecast",
        title: "Retail forecasting platform",
        text: "Verified synthetic case study: Python forecast service with documented evaluation.",
      },
      {
        evidence_id: "case-api",
        title: "Multi-tenant analytics API",
        text: "Verified synthetic case study: FastAPI, PostgreSQL, Next.js and Playwright.",
      },
    ],
  },
};

const analytics = {
  generated_at: "2026-11-11T00:00:00Z",
  scope: "Synthetic simulator outcomes and synthetic persona retrieval benchmark",
  personas: {
    "ai-ml-engineer": { jobs: 30, bid_or_skip_f1: 1, scam_precision: 1, scam_recall: 1, reply_rate: 0.667, hire_rate: 0.583, p95_latency_seconds: 0.01 },
    "full-stack-developer": { jobs: 30, bid_or_skip_f1: 1, scam_precision: 1, scam_recall: 1, reply_rate: 0.917, hire_rate: 0.667, p95_latency_seconds: 0.01 },
    "data-analyst": { jobs: 30, bid_or_skip_f1: 1, scam_precision: 1, scam_recall: 1, reply_rate: 0.708, hire_rate: 0.542, p95_latency_seconds: 0.01 },
  },
  rag_variants: {
    v0_dense: { evidence_recall_at_5: 0.494, ndcg_at_10: 0.738, unsupported_claims_after: 0, p95_latency_ms: 2.5 },
    v2_hybrid: { evidence_recall_at_5: 0.499, ndcg_at_10: 0.796, unsupported_claims_after: 0, p95_latency_ms: 119 },
  },
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await page.addInitScript(() => localStorage.setItem("gigbid_token", "demo-token"));
await page.route("http://localhost:8000/**", async (route) => {
  const url = new URL(route.request().url());
  const path = url.pathname;
  if (path === "/health") return route.fulfill({ json: { status: "ok", service: "gigbid-api", dependencies: { marketplace: "available", checkpointer: "postgres" } } });
  if (path === "/api/jobs/ranked/inbox") return route.fulfill({ json: jobs });
  if (path === "/api/profile") return route.fulfill({ json: profile });
  if (path === "/api/pipeline") return route.fulfill({ json: { cards: [{ job_id: "job-python-1", title: jobs[0].title, status: "draft", connects_spent: 8, updated_at: "2026-11-11T00:00:00Z" }] } });
  if (path === "/api/runs/run-1") return route.fulfill({ json: run });
  if (path === "/api/runs/run-1/history") return route.fulfill({ json: { thread_id: "run-1", checkpoints: [{ checkpoint_id: "checkpoint-approval", created_at: "2026-11-11T00:00:00Z", status: "awaiting_approval", next_nodes: ["approval"], step_count: 8 }, { checkpoint_id: "checkpoint-analysis", created_at: "2026-11-11T00:00:00Z", status: "analysing", next_nodes: ["pricing"], step_count: 4 }] } });
  if (path === "/api/runs/run-1/events") return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: status\ndata: {\"status\":\"awaiting_approval\"}\n\n" });
  if (path === "/api/analytics") return route.fulfill({ json: analytics });
  return route.fulfill({ status: 404, json: { detail: `No demo fixture for ${path}` } });
});

for (const [index, path] of ["/inbox", "/runs/run-1", "/studio/run-1", "/analytics"].entries()) {
  await page.goto(`${baseURL}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: resolve(output, `frame-${index + 1}.png`), fullPage: false });
}

await browser.close();
console.log(output);
