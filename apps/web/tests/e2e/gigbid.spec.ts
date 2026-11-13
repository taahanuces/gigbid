import { expect, test, type Page } from "@playwright/test";

const approvalPayload = {
  thread_id: "run-1",
  status: "awaiting_approval",
  trace_id: "trace-e2e-4016",
  trace_url: "https://traces.example.test/trace/trace-e2e-4016",
  state: {
    events: [{ node: "analyst", status: "complete" }],
    approval_payload: {
      dry_run: { tool_name: "create_proposal_draft", connects_cost: 7, side_effects: ["Creates a draft"] },
      risk_report: { explanation: "Low risk client." },
    },
    compliance_verdict: { passed: true, blocked_rule_ids: [], comments: ["Policy checks passed."] },
    proposal_draft: { cover_letter: "Original grounded proposal." },
    evidence: [
      { evidence_id: "case-1", title: "Forecast project", text: "Verified evidence." },
    ],
  },
};

const profilePayload = {
  settings: {
    persona: "data-analyst",
    hourly_rate: 35,
    fixed_price_floor: 300,
    weekly_connects_budget: 80,
    max_connects_per_bid: 16,
    search_keywords: ["python", "analytics"],
    approval_required: true,
    onboarding_complete: false,
  },
  marketplace_mode: "gigsim",
  evidence_count: 30,
  data_origin: "synthetic persona portfolio; public jobs",
};

async function healthy(page: Page) {
  await page.route("**/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        service: "gigbid-api",
        dependencies: { marketplace: "available", checkpointer: "memory" },
      },
    }),
  );
}

async function runWithHistory(page: Page) {
  await page.route("**/api/runs/run-1", (route) => route.fulfill({ json: approvalPayload }));
  await page.route("**/api/runs/run-1/history", (route) =>
    route.fulfill({
      json: {
        thread_id: "run-1",
        checkpoints: [
          {
            checkpoint_id: "checkpoint-001",
            created_at: "2026-11-11T00:00:00Z",
            status: "analysing",
            next_nodes: ["risk_assessor", "fit_matcher"],
            step_count: 1,
          },
        ],
      },
    }),
  );
}

async function profile(page: Page) {
  await page.route("**/api/profile", (route) => route.fulfill({ json: profilePayload }));
}

async function emptyPortfolio(page: Page) {
  await page.route("**/api/portfolio", (route) => route.fulfill({ json: [] }));
}

test("onboarding persists the selected portfolio and bidding boundaries", async ({ page }) => {
  await healthy(page);
  let saved = false;
  await page.route("**/api/profile", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: profilePayload });
      return;
    }
    const body = await route.request().postDataJSON();
    expect(body).toMatchObject({
      persona: "full-stack-developer",
      fixed_price_floor: 725,
      approval_required: true,
      onboarding_complete: true,
    });
    saved = true;
    await route.fulfill({ json: { ...profilePayload, settings: body } });
  });
  await page.route("**/api/jobs", (route) => route.fulfill({ json: [] }));
  await emptyPortfolio(page);
  await page.route("**/api/portfolio/upload", (route) => route.fulfill({
    json: [{
      evidence_id: "upload-case-1",
      tenant_id: "demo",
      persona: "full-stack-developer",
      type: "case_study",
      title: "Private case",
      text: "Built a Next.js application.",
      source: "upload://private-case.md",
      skills: ["Next.js"],
      data_origin: "private_user_data_not_committed",
      relevance_score: 0,
    }],
  }));
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "Onboarding" })).toBeVisible();
  await page.getByLabel("Portfolio persona").selectOption("full-stack-developer");
  await page.getByLabel("Fixed-price floor (USD)").fill("725");
  await page.getByLabel("Portfolio file").setInputFiles({
    name: "private-case.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Private case\nBuilt a Next.js application."),
  });
  await page.getByLabel("Portfolio skills").fill("Next.js");
  await page.getByRole("button", { name: "Upload and index" }).click();
  await expect(page.getByText("1 evidence chunk indexed.")).toBeVisible();
  await page.getByRole("button", { name: "Save and open job inbox" }).click();
  await expect.poll(() => saved).toBe(true);
  await expect(page).toHaveURL(/\/inbox$/);
});

test("approving a proposal resumes the interrupted run", async ({ page }) => {
  await healthy(page);
  await runWithHistory(page);
  await page.route("**/api/runs/run-1/approval", async (route) => {
    expect((await route.request().postDataJSON()).action).toBe("approve");
    await route.fulfill({ json: { ...approvalPayload, status: "draft_created" } });
  });
  await page.goto("/runs/run-1");
  await expect(page.getByText("trace-e2e-4016")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open trace viewer" })).toHaveAttribute(
    "href",
    "https://traces.example.test/trace/trace-e2e-4016",
  );
  const approve = page.getByRole("button", { name: "Approve draft" });
  await approve.evaluate((element: HTMLButtonElement) => element.click());
  await expect(page.getByText("Thread run-1 · draft_created")).toBeVisible({ timeout: 10_000 });
});

test("rejecting requires and submits a human reason", async ({ page }) => {
  await healthy(page);
  await runWithHistory(page);
  await page.route("**/api/runs/run-1/approval", async (route) => {
    const body = await route.request().postDataJSON();
    expect(body).toMatchObject({ action: "reject", reason: "Budget is outside my floor" });
    await route.fulfill({ json: { ...approvalPayload, status: "rejected" } });
  });
  await page.goto("/runs/run-1");
  const reject = page.getByRole("button", { name: "Reject", exact: true });
  await reject.evaluate((element: HTMLButtonElement) => element.click());
  await page.getByLabel("Reason for rejection").fill("Budget is outside my floor");
  await page
    .getByRole("button", { name: "Confirm rejection" })
    .evaluate((element: HTMLButtonElement) => element.click());
  await expect(page.getByText("Thread run-1 · rejected")).toBeVisible({ timeout: 10_000 });
});

test("checkpoint history replays a prior state read-only", async ({ page }) => {
  await healthy(page);
  await runWithHistory(page);
  await page.route("**/api/runs/run-1/replay/checkpoint-001", (route) =>
    route.fulfill({
      json: {
        thread_id: "run-1",
        checkpoint_id: "checkpoint-001",
        read_only: true,
        status: "analysing",
        next_nodes: ["risk_assessor", "fit_matcher"],
        state: { events: [{ node: "load_job", status: "complete" }] },
      },
    }),
  );
  await page.goto("/runs/run-1");
  await page.getByRole("button", { name: /analysing/i }).click();
  await expect(page.getByText(/Read-only checkpoint replay/)).toBeVisible();
  await expect(page.getByText("load job")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve draft" })).toHaveCount(0);
});

test("editing a draft sends the changed text through compliance", async ({ page }) => {
  await healthy(page);
  await page.route("**/api/runs/run-1", (route) => route.fulfill({ json: approvalPayload }));
  await page.route("**/api/runs/run-1/approval", async (route) => {
    const body = await route.request().postDataJSON();
    expect(body.action).toBe("edit");
    expect(body.edited_cover_letter).toContain("human revision");
    await route.fulfill({ json: approvalPayload });
  });
  await page.route("**/api/runs/run-1/regenerate-paragraph", async (route) => {
    expect((await route.request().postDataJSON()).paragraph_index).toBe(0);
    await route.fulfill({
      json: {
        paragraph_index: 0,
        replacement: "Regenerated grounded opening [case-1].",
        reasons: ["verified_evidence_only"],
      },
    });
  });
  await page.goto("/studio/run-1");
  await expect(page.getByText("Policy checks passed.")).toBeVisible();
  await expect(page.getByText(/7 Connects/)).toBeVisible();
  await page.getByRole("button", { name: "Regenerate paragraph" }).click();
  await expect(page.getByLabel("Proposal cover letter")).toHaveValue(/Regenerated grounded opening/);
  await page.getByLabel("Proposal cover letter").fill("A human revision grounded in case-1.");
  await page.getByRole("button", { name: "Save edit" }).click({ force: true });
  await expect(page.getByText("Edit saved and sent back through compliance.")).toBeVisible();
});

test("marketplace outage produces a clear degraded-mode banner", async ({ page }) => {
  await page.route("**/health", (route) =>
    route.fulfill({
      json: {
        status: "degraded",
        service: "gigbid-api",
        dependencies: { marketplace: "unavailable", checkpointer: "memory" },
      },
    }),
  );
  await profile(page);
  await emptyPortfolio(page);
  await page.route("**/api/memories", (route) => route.fulfill({ json: [] }));
  await page.goto("/settings");
  await expect(page.getByRole("status")).toContainText("Marketplace unavailable");
});

test("analytics displays committed synthetic evaluation scope", async ({ page }) => {
  await healthy(page);
  await page.route("**/api/analytics", (route) => route.fulfill({
    json: {
      generated_at: "2026-11-11T00:00:00Z",
      scope: "Synthetic simulator outcomes and synthetic persona retrieval benchmark",
      personas: {
        "ai-ml-engineer": { jobs: 30, bid_or_skip_f1: 1, scam_precision: 1, scam_recall: 1, reply_rate: 0.67, hire_rate: 0.58, p95_latency_seconds: 0.01, proposals_submitted: 24, model_tokens: 0, model_cost_usd: 0 },
      },
      rag_variants: {
        v2_hybrid: { evidence_recall_at_5: 0.499, ndcg_at_10: 0.796, unsupported_claims_after: 0, p95_latency_ms: 119 },
      },
      categories: {
        SaaS: { proposals: 6, reply_rate: 0.83, hire_rate: 0.67, connects_spent: 48 },
      },
      connects_spent: 576,
      top_rejection_reasons: { prompt_injection: 18, off_platform_contact: 18 },
    },
  }));
  await page.goto("/analytics");
  await expect(page.getByText("Synthetic simulator outcomes and synthetic persona retrieval benchmark")).toBeVisible();
  await expect(page.getByText("67%").first()).toBeVisible();
  await expect(page.getByText("v2_hybrid")).toBeVisible();
  await expect(page.getByText("576")).toBeVisible();
  await expect(page.getByText(/prompt injection · 18/i)).toBeVisible();
});

test("job detail renders the durable analysis, evidence matrix and price rationale", async ({ page }) => {
  await healthy(page);
  const job = {
    job_id: "job-python-1",
    client_id: "client-1",
    title: "Analytics API and forecasting dashboard",
    description: "Build a tested forecasting API and dashboard.",
    required_skills: ["FastAPI", "PostgreSQL"],
    connects_cost: 8,
    budget: { min: 1800, max: 2600, currency: "USD" },
  };
  await page.route("**/api/jobs/job-python-1", (route) => route.fulfill({ json: job }));
  await page.route("**/api/jobs/ranked/inbox", (route) => route.fulfill({ json: [{ ...job, thread_id: "run-1", analysis_status: "awaiting_approval", action: "bid", fit_score: 1, risk_score: 0.08, recommended_price: 2400, reasons: ["Strong evidence"] }] }));
  await page.route("**/api/runs/run-1", (route) => route.fulfill({ json: {
    ...approvalPayload,
    state: {
      ...approvalPayload.state,
      fit_report: { score: 1, explanation: "2 of 2 requirements have evidence.", requirement_matrix: [{ requirement: "FastAPI", evidence_ids: ["case-api"], supported: true, explanation: "Supported." }, { requirement: "PostgreSQL", evidence_ids: ["case-api"], supported: true, explanation: "Supported." }] },
      risk_report: { score: 0.08, flags: [], explanation: "Low-risk client." },
      decision: { action: "bid", confidence: 0.94, reasons: ["Every required skill has verified evidence."] },
      price_quote: { amount: 2400, currency: "USD", fair_band_min: 2100, fair_band_max: 2600, floor_amount: 500, rationale: "Inside the public market band and above the user floor.", market_prior_category: "software-development", market_prior_sample_size: 1200 },
      evidence: [{ evidence_id: "case-api", title: "Verified analytics API", text: "FastAPI and PostgreSQL case study." }],
    },
  } }));

  await page.goto("/jobs/job-python-1");
  await expect(page.getByText("2 of 2 requirements have evidence.")).toBeVisible();
  await expect(page.getByText("Verified analytics API").first()).toBeVisible();
  await expect(page.getByText("2400 USD")).toBeVisible();
  await expect(page.getByText("Every required skill has verified evidence.")).toBeVisible();
});

test("pipeline groups marketplace cards by observed status", async ({ page }) => {
  await healthy(page);
  await page.route("**/api/pipeline", (route) => route.fulfill({
    json: {
      cards: [{ proposal_id: "proposal-1", job_id: "job-1", title: "Forecast demand", status: "replied", connects_spent: 8, data_origin: "synthetic_rule_based" }],
    },
  }));
  await page.goto("/pipeline");
  await expect(page.getByRole("heading", { name: "Forecast demand" })).toBeVisible();
  await expect(page.getByText("synthetic rule based")).toBeVisible();
});

test("promoted memory is inspectable and deletable", async ({ page }) => {
  await healthy(page);
  await profile(page);
  await emptyPortfolio(page);
  await page.route("**/api/memories", (route) =>
    route.fulfill({
      json: [
        {
          key: "memory-1",
          kind: "style",
          value: "prefer_concise_proposals",
          evidence_count: 3,
          category: null,
          promoted_at: "2026-11-10T18:00:00Z",
        },
      ],
    }),
  );
  await page.route("**/api/memories/style/memory-1", async (route) => {
    expect(route.request().method()).toBe("DELETE");
    await route.fulfill({ status: 204 });
  });
  await page.goto("/settings");
  await expect(page.getByText("prefer concise proposals")).toBeVisible();
  await page.getByRole("button", { name: "Forget prefer_concise_proposals" }).click();
  await expect(page.getByText("prefer concise proposals")).toHaveCount(0);
});

test("public trace evidence is available without reviewer authentication", async ({ page }) => {
  await page.goto("/traces");
  await expect(page.getByRole("heading", { name: "Read-only agent traces" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Scam and prompt-injection job skipped/ })).toBeVisible();

  await page.goto("/traces/approved-critic-loop");
  await expect(page.getByRole("heading", { name: "Critic revision loop and approved draft" })).toBeVisible();
  await expect(page.getByText("trace-public-critic-4016")).toBeVisible();
  await expect(page.getByText("The graph interrupted for explicit human approval before the write.")).toBeVisible();
  await expect(page.getByText("Synthetic · redacted · read-only")).toBeVisible();
});
