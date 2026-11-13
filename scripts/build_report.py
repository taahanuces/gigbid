# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/GigBid_AI-4016_RnD_Report.pdf"

GREEN = colors.HexColor("#187449")
DARK = colors.HexColor("#11251f")
MUTED = colors.HexColor("#52625d")
PAPER = colors.HexColor("#f4f3ed")
MINT = colors.HexColor("#e5f6e9")
LINE = colors.HexColor("#d8ddd7")
RED = colors.HexColor("#a94235")


def _header_footer(canvas: object, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(18 * mm, A4[1] - 11 * mm, "GIGBID - AI-4016 ENGINEERING DESIGN REVIEW")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=30,
            leading=34,
            textColor=DARK,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=DARK,
            spaceAfter=9,
            spaceBefore=2,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=GREEN,
            spaceBefore=9,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13,
            textColor=DARK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=10,
            textColor=MUTED,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=DARK,
            borderColor=GREEN,
            borderWidth=1,
            borderPadding=9,
            backColor=MINT,
            spaceBefore=7,
            spaceAfter=9,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=DARK,
            alignment=TA_LEFT,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.1,
            leading=9,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=DARK,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _table(
    rows: list[list[str]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    repeat: bool = True,
) -> Table:
    data = [
        [
            _p(cell, styles["table_head"] if row_index == 0 else styles["table"])
            for cell in row
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(data, colWidths=widths, repeatRows=1 if repeat else 0, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
            ]
        )
    )
    return table


def _architecture(styles: dict[str, ParagraphStyle]) -> Table:
    boxes = [
        ["Next.js UI", "FastAPI", "Celery + Redis", "LangGraph"],
        ["Approval + SSE", "Typed API + auth", "Durable long runs", "Bid + conversation"],
        ["Portfolio MCP", "Marketplace MCP", "Workspace MCP", "Postgres + RAG"],
    ]
    table = Table(
        [[_p(cell, styles["center"]) for cell in row] for row in boxes],
        colWidths=[41 * mm] * 4,
        rowHeights=[16 * mm, 13 * mm, 16 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.8, GREEN),
                ("BACKGROUND", (0, 0), (-1, 0), MINT),
                ("BACKGROUND", (0, 2), (-1, 2), PAPER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=19 * mm,
        title="GigBid AI-4016 R&D Report",
        author="Taaha Khan",
        subject="Engineering design review",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_header_footer)])
    story: list[object] = []

    story.extend(
        [
            Spacer(1, 24 * mm),
            _p("GigBid", styles["title"]),
            _p(
                "A human-controlled multi-agent freelancer copilot",
                styles["subtitle"],
            ),
            Spacer(1, 3 * mm),
            _p(
                "AI-4016 R&D Assignment - Engineering Design Review<br/>"
                "LangGraph, advanced RAG, MCP, FastAPI, Next.js, Postgres, Redis and open models",
                styles["callout"],
            ),
            Spacer(1, 8 * mm),
            _table(
                [
                    ["Author", "Course", "Prepared", "Report scope"],
                    [
                        "Taaha Khan",
                        "AI-4016 Agentic AI",
                        "12 November 2026",
                        "Local evidence plus a live Render reviewer deployment",
                    ],
                ],
                [35 * mm, 39 * mm, 34 * mm, 60 * mm],
                styles,
                repeat=False,
            ),
            Spacer(1, 10 * mm),
            _p("Executive summary", styles["h1"]),
            _p(
                "GigBid discovers jobs, evaluates fit and risk, prices work, retrieves verifiable "
                "portfolio evidence, drafts cited proposals, and pauses before every marketplace or "
                "message write. The implementation owns three MCP servers, places GigSim and Upwork "
                "behind one port, persists LangGraph interrupts in Postgres, streams run checkpoints "
                "to a responsive UI, and moves long runs and saved searches to Celery.",
                styles["body"],
            ),
            _p(
                "The strongest retrieval finding was negative: requirement decomposition reduced "
                "Recall@5, and lexical-only ranking beat type-diverse hybrid RRF on the authored "
                "synthetic benchmark. V2 still ships for maximum Recall@5, semantic/type coverage and "
                "claim grounding. A separate measured writer study selected Qwen3 4B over Llama 3.1 "
                "8B. A Render reviewer deployment is live; no human, hidden-test or live-marketplace "
                "result is invented.",
                styles["body"],
            ),
            _p(
                "Live reviewer: https://gigbid-web.onrender.com. Evidence: evals/results/*.json; "
                "docs/RAG_EXPERIMENT.md; docs/DEPLOYMENT_EVIDENCE.md",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("1. Problem, constraints and architecture", styles["h1"]),
            _p(
                "Freelancers waste time on weak jobs, spend scarce Connects, and risk sending generic "
                "or non-compliant proposals. GigBid may automate discovery, analysis and drafting; it "
                "must never auto-send a proposal or message, fabricate experience, scrape a platform, "
                "follow instructions embedded in marketplace content, or spend Connects without a "
                "human interrupt.",
                styles["body"],
            ),
            _architecture(styles),
            _p("State and trust boundaries", styles["h2"]),
            _p(
                "Job state contains only the current typed hand-offs. Execution history is checkpointed "
                "and traced. Long-term style and outcome memories are stored only after explicit "
                "promotion thresholds. Marketplace effects cross MarketplacePort; the graph cannot tell "
                "whether the adapter is memory, the self-contained simulator, or official Upwork MCP.",
                styles["body"],
            ),
            _table(
                [
                    ["Invariant", "Implementation", "Verification"],
                    ["Human before writes", "interrupt() plus dry-run approval payload", "Approval, edit, reject and exactly-once tests"],
                    ["Grounded claims", "Evidence IDs plus post-draft verification", "Seeded unsupported claim: 1 before, 0 after"],
                    ["Durability", "Postgres saver/store and idempotency keys", "Restart/resume integration test"],
                    ["Budgets", "Step, token, price and Connects limits", "Needs-attention and profile-boundary tests"],
                    ["Isolation", "Tenant/user namespaces and bearer auth", "Cross-scope checks and private portfolio store"],
                ],
                [39 * mm, 70 * mm, 59 * mm],
                styles,
            ),
            _p(
                "Declared targets: p95 job analysis <= 45 s; p95 proposal <= 90 s; open-profile model "
                "cost USD 0 locally. The deterministic simulator study measured sub-0.01 s graph "
                "latency, but this is not an LLM production latency claim. [agent/config.yaml; "
                "evals/results/simulator_outcomes.json]",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("2. R&D A - MCP tool design", styles["h1"]),
            _p(
                "Hypothesis: fine-grained tools with specific descriptions improve correct selection "
                "and arguments over server-sized coarse tools, at a token cost. Forty known-call tasks "
                "were run through three designs using the same local llama3.1:8b model, temperature 0 "
                "and seed 4016. The study covers 120 calls and reports exact tool/argument matches.",
                styles["body"],
            ),
            _table(
                [
                    ["Design", "Tool accuracy", "Argument accuracy", "Tokens/task", "p95 ms"],
                    ["Fine-grained", "1.00", "0.60", "1229.6", "5485"],
                    ["Coarse", "0.80", "0.15", "411.0", "6061"],
                    ["Best descriptions", "1.00", "0.50", "1424.0", "7740"],
                ],
                [42 * mm, 31 * mm, 34 * mm, 29 * mm, 28 * mm],
                styles,
            ),
            _p("Decision", styles["h2"]),
            _p(
                "Ship single-purpose tools with strict Pydantic inputs. Fine-grained tools tied for "
                "perfect selection and produced the best argument accuracy. Rewritten descriptions did "
                "not improve arguments and increased tokens, so description length alone is not a fix. "
                "The result is one-model evidence, not a universal model conclusion.",
                styles["body"],
            ),
            _p("Owned and third-party surface", styles["h2"]),
            _table(
                [
                    ["Server", "Surface", "Controls"],
                    ["Portfolio", "search evidence, case study, skills; resources and prompt", "Read-only, bearer auth, tenant metadata"],
                    ["Marketplace", "jobs, clients, Connects, messages, proposal/message writes", "Dry run, idempotency, rate limit, audit log"],
                    ["Workspace", "slots, tentative holds, email drafts", "Local mock, approval before writes"],
                    ["Upwork + GitHub", "Official remote MCP endpoints", "Encrypted token boundary, allowlisted tools, no scraping"],
                ],
                [38 * mm, 67 * mm, 63 * mm],
                styles,
            ),
            _p(
                "Sources: evals/results/tool_design.json; docs/TOOL_DESIGN_EXPERIMENT.md; "
                "docs/TOOLS.md; tests/contract/",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("3. R&D B - Evidence retrieval and verification", styles["h1"]),
            _p(
                "Ninety authored synthetic jobs (30 per persona) were evaluated against synthetic "
                "portfolio evidence. Each job has ten relevant items, so Recall@5 has a ceiling of 0.5. "
                "The preregistered hypothesis that V1, V2 and V3 all match or beat V0 failed.",
                styles["body"],
            ),
            _table(
                [
                    ["Variant", "Recall@5", "MRR", "nDCG@10", "Attack unsupported before/after", "p95 ms"],
                    ["V0 dense", "0.494", "0.989", "0.738", "1 / 0", "2.5"],
                    ["V1 requirements", "0.378", "0.664", "0.662", "1 / 0", "17.0"],
                    ["V2 hybrid", "0.500", "1.000", "0.801", "1 / 0", "120.4"],
                    ["V3 rerank", "0.498", "1.000", "0.749", "1 / 0", "120.4"],
                    ["V8 corrective", "0.378", "0.664", "0.662", "1 / 0", "17.1"],
                ],
                [28 * mm, 21 * mm, 19 * mm, 23 * mm, 49 * mm, 23 * mm],
                styles,
            ),
            _p("Ablation and shipped choice", styles["h2"]),
            _table(
                [
                    ["Configuration", "Recall@5", "nDCG@10", "p95 ms"],
                    ["Dense only", "0.493", "0.742", "2.5"],
                    ["Lexical only", "0.500", "0.833", "180.2"],
                    ["Hybrid + type cap", "0.500", "0.801", "182.6"],
                ],
                [53 * mm, 35 * mm, 39 * mm, 35 * mm],
                styles,
            ),
            _p(
                "Lexical-only beat type-diverse hybrid by 0.032 nDCG, so the ablation hypothesis failed. "
                "V2 ships for maximum Recall@5, semantic paraphrases and evidence-type coverage: its "
                "cap prevents past proposals crowding case/code/review evidence out of writer context. "
                "This is a grounding trade-off, not a claim that fusion won. "
                "The verifier now discovers material claims even when writer metadata omits them, then "
                "removes or narrows anything unsupported before the Critic.",
                styles["body"],
            ),
            _p(
                "Judge calibration and blind-panel packets are generated but unscored. Thirty author "
                "labels and independent classmate ratings are required; the scripts intentionally emit "
                "no kappa or preference result until humans fill them. [evals/results/synthetic_rag.json; "
                "evals/results/rag_ablation.json; evals/results/judge_calibration.json]",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("4. R&D C - Multi-agent orchestration", styles["h1"]),
            _p(
                "The bid graph fans Job Analyst, Risk Assessor and Fit Matcher out after load, joins "
                "their typed outputs, then routes skip/watch/bid. Bid runs continue through pricing, "
                "writer, verifier, a maximum two-pass Critic loop, compliance and approval. The "
                "conversation graph classifies client messages, proposes answers or interview slots, "
                "and interrupts before send.",
                styles["body"],
            ),
            _table(
                [
                    ["Control policy", "Completion", "Injection recall", "Mean control steps", "p95 ms", "Writes"],
                    ["Hand-built", "1.00", "1.00", "4", "7.19", "0"],
                    ["Supervisor-style", "1.00", "1.00", "8", "7.22", "0"],
                    ["ReAct-style", "1.00", "1.00", "8", "7.15", "0"],
                ],
                [39 * mm, 27 * mm, 31 * mm, 35 * mm, 21 * mm, 15 * mm],
                styles,
            ),
            _p("Model-backed frozen GigSim slice", styles["h2"]),
            _table(
                [
                    ["Model / policy", "Controller completion", "Final F1", "Safety violations", "p95 s"],
                    ["Qwen / hand", "0.833", "1.00", "0", "30.0"],
                    ["Qwen / supervisor", "1.000", "1.00", "0", "4.1"],
                    ["Qwen / ReAct", "0.833", "1.00", "0", "19.0"],
                    ["Llama / hand", "1.000", "1.00", "0", "4.2"],
                    ["Llama / supervisor", "1.000", "1.00", "0", "7.5"],
                    ["Llama / ReAct", "1.000", "1.00", "0", "16.3"],
                ],
                [45 * mm, 40 * mm, 24 * mm, 35 * mm, 22 * mm],
                styles,
            ),
            _p("Interpretation", styles["h2"]),
            _p(
                "The public baseline policies agreed because they share deterministic nodes. The separate "
                "36-row real-model study froze six direct/attack jobs, budgets and one retry injection. "
                "Every final action was correct and safe, but Qwen failed the controller schema once in "
                "hand and once in ReAct; the bounded fallback preserved the outcome. Llama completed all "
                "rows. ReAct used the most tokens and latency. With no decision or synthetic-outcome gain, "
                "the explicit hand-built graph remains the production boundary.",
                styles["body"],
            ),
            _p("Durability and failure handling", styles["h2"]),
            _p(
                "The API seeds a Postgres START checkpoint and returns a queued thread. Celery verifies "
                "tenant/user/job identity, resumes the exact thread, and writes a ranked inbox summary. "
                "Approval state survives API restart. Every marketplace write reuses an idempotency key. "
                "Workers acknowledge late, retry bounded connection failures, and place terminal failures "
                "in a PII-redacted, bounded Redis dead-letter list. The writer tries its configured open "
                "model, then the small fallback, then a deterministic grounded fallback.",
                styles["body"],
            ),
            _p(
                "Sources: evals/results/agent_design.json; evals/results/agent_model_design.json; "
                "docs/AGENT_MODEL_DESIGN_EXPERIMENT.md; "
                "tests/integration/test_postgres_durability.py; worker/tasks.py",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("5. Product and production engineering", styles["h1"]),
            _p(
                "The typed Next.js application includes sign-in, persisted onboarding, a ranked inbox, "
                "job detail, live run timeline, proposal studio, pipeline, messages, analytics and "
                "settings. Users choose a persona, rates, filters and Connects limits, and can upload "
                "private PDF/Markdown/text evidence. Every claim exposes evidence on hover. Paragraph "
                "regeneration returns to verification; approvals resume the interrupted thread.",
                styles["body"],
            ),
            _table(
                [
                    ["Area", "Implementation evidence"],
                    ["Streaming", "Authenticated SSE polls durable checkpoints and de-duplicates node events"],
                    ["API contract", "FastAPI OpenAPI regenerates the TypeScript client"],
                    ["Responsive UI", "20 Playwright cases pass: 10 flows on desktop and mobile"],
                    ["Background work", "Celery long runs, beat saved searches, Redis dedupe/DLQ"],
                    ["Packaging", "Compose full stack plus live Render web/API/Postgres reviewer profile"],
                    ["Evaluation CI", "make eval plus regression thresholds; unit, contract and UI workflows"],
                ],
                [42 * mm, 124 * mm],
                styles,
            ),
            _p("Open models and observability", styles["h2"]),
            _p(
                "The same nine fixed synthetic jobs were run per model with temperature 0, seed 4016, "
                "identical type-diverse V2 evidence and one excluded warm-up. Both candidates achieved "
                "perfect validity/grounding; the registered rule selected Qwen3 4B on personalization "
                "and latency. Llama 3.1 8B is the model fallback before the deterministic writer.",
                styles["body"],
            ),
            _table(
                [
                    ["Writer", "Valid/citations", "Unsupported after", "Personalization", "p95 s"],
                    ["Qwen3 4B (primary)", "1.00 / 1.00", "0.00", "0.630", "11.4"],
                    ["Llama 3.1 8B", "1.00 / 1.00", "0.00", "0.556", "33.5"],
                ],
                [42 * mm, 34 * mm, 35 * mm, 34 * mm, 21 * mm],
                styles,
            ),
            _p(
                "The reviewer is live at https://gigbid-web.onrender.com; its hosted graph produced five "
                "events and five Postgres checkpoints. Phoenix received a content-free OTLP span locally; "
                "public read-only trace URLs still require secured deployment. "
                "[evals/results/model_profiles.json; docs/MODEL_PROFILE_EXPERIMENT.md]",
                styles["small"],
            ),
            Spacer(1, 2 * mm),
            _p(
                "Simulator outcome study (synthetic rule engine): 90 jobs, bid/skip F1 1.00 and scam "
                "recall 1.00 for every persona; reply rates 0.667 AI/ML, 0.917 full-stack and 0.708 data; "
                "hire rates 0.583, 0.667 and 0.542. These are simulator plumbing outcomes, not real "
                "marketplace causality. [evals/results/simulator_outcomes.json]",
                styles["callout"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("6. Change request and signature extension", styles["h1"]),
            _p("Configuration-driven policy change", styles["h2"]),
            _p(
                "Policy rules, Connects thresholds, rate limits, schedules and model routing live in "
                "versioned configuration instead of node prompts. A new platform rule is added to the "
                "policy pack and compliance evaluator, then covered by an attack test; graph topology "
                "and marketplace adapters do not change. Because the instructor's final 2 November "
                "change text was not included in the available material, this report does not fabricate "
                "a line count or elapsed time for that change.",
                styles["body"],
            ),
            _p("X3 Portfolio Builder", styles["h2"]),
            _p(
                "GitHub's official MCP server is allowlisted for repository reads. The builder detects "
                "technologies in README/code, quarantines unverifiable outcome claims, and produces a "
                "pending candidate. Only explicit approval converts the code-verifiable summary into a "
                "private portfolio evidence item.",
                styles["body"],
            ),
            _table(
                [
                    ["Synthetic repository study (n=12)", "Result"],
                    ["Technology precision", "1.00"],
                    ["Technology recall", "1.00"],
                    ["Unsupported outcome-claim recall", "1.00"],
                    ["False-positive rate", "0.00"],
                    ["Human approval required", "100%"],
                ],
                [115 * mm, 48 * mm],
                styles,
            ),
            _p(
                "The fixtures test parsing and safety, not live GitHub accuracy. Live validation and "
                "reviewer acceptance need a user token and human review. [evals/results/portfolio_builder.json; "
                "docs/EXTENSION.md]",
                styles["small"],
            ),
            _p("Data and provenance", styles["h2"]),
            _p(
                "The simulator uses 300 Apache-2.0 public Kaggle jobs and explicitly synthetic client "
                "preferences, gold labels and outcomes. Persona portfolios, proposals, conversations and "
                "repository snapshots are synthetic. Public contracts supply descriptive pricing priors. "
                "Private uploads are tenant-scoped and ignored by version control. Licenses, hashes, "
                "transforms and limitations are recorded in docs/DATA_CARD.md and data/sources.yaml.",
                styles["body"],
            ),
            PageBreak(),
        ]
    )

    failure_rows = [
        ["Failure class", "Observed example", "Fix / status"],
        ["Missed evidence", "V1 over-weighted broad repeated requirements", "Keep V2; tune only on training split"],
        ["Retrieval fusion", "Lexical 0.833 vs type-diverse hybrid 0.801", "Report loss; retain grounding/type coverage"],
        ["Reasoning runaway", "Default thinking ran for minutes", "Disable thinking; word/token caps"],
        ["Mispricing", "Open-ended public budgets produced null min/max", "Nullable schema and user-floor precedence"],
        ["Unsupported claim", "Injected 300% guarantee", "Auto-discover material claims; verifier removes it"],
        ["Citation contract", "Models paraphrased IDs/past-proposal claims", "Exact brackets, type cap, verifier rule"],
        ["Compliance miss", "Off-platform contact embedded in content", "Policy pack plus sanitization and block reason"],
        ["Prompt injection", "Job tells agent to ignore rules", "Untrusted delimiters, risk flag, zero write path"],
        ["Tool argument", "Fine-grained argument accuracy only 0.60", "Strict schemas; do not trust selection alone"],
        ["Marketplace failure", "429/5xx/fault injection", "Backoff, degraded UI, durable queue and DLQ"],
        ["Model failure", "Missing/unavailable local model", "Small-model then deterministic grounded fallback"],
        ["UI policy bug", "Frontend hard-coded USD 300 floor", "Inherit persisted profile; API regression test"],
    ]
    story.extend(
        [
            _p("7. Failure analysis", styles["h1"]),
            _p(
                "Failures were grouped by system boundary rather than hidden behind aggregate averages. "
                "This page selects twelve report-sized rows from the sixteen-class taxonomy in "
                "docs/FAILURE_ANALYSIS.md, including public-data, UI, model-reasoning and citation defects.",
                styles["body"],
            ),
            _table(failure_rows, [35 * mm, 65 * mm, 66 * mm], styles),
            Spacer(1, 4 * mm),
            _p(
                "The main lesson is that deterministic safety structure and typed contracts catch "
                "different failures than model quality. Better prompts would not have fixed nullable "
                "budgets, a hard-coded UI floor, duplicate writes or lost approval state.",
                styles["callout"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("8. Safety, limitations and completion boundary", styles["h1"]),
            _p("What GigBid must never do", styles["h2"]),
            _p(
                "Never scrape, use session cookies, auto-submit, bypass final platform confirmation, "
                "spend Connects without approval, reveal OAuth secrets, log unmasked PII, follow job or "
                "message instructions, or state experience not supported by portfolio evidence. These "
                "constraints are enforced by port boundaries, tool allowlists, interrupts, idempotency, "
                "policy checks, claim verification, tenant namespaces and redacted audit/dead-letter logs.",
                styles["body"],
            ),
            _p("Honest limitations", styles["h2"]),
            _table(
                [
                    ["Pending item", "Why it cannot be generated locally"],
                    ["30 author labels + Cohen kappa", "Requires the student to inspect and label all items"],
                    ["Blind classmate panel", "Requires independent human raters"],
                    ["Hidden test results", "Instructor-only dataset and post-deadline run"],
                    ["Optional GitHub live validation", "Requires the user's PAT and consented repositories"],
                    ["External traces, video and publication", "Public app is live; these still require secure hosting or human publication"],
                    ["Exact change-request diff", "Final instructor policy update text was not supplied"],
                ],
                [62 * mm, 104 * mm],
                styles,
            ),
            _p("Conclusion", styles["h2"]),
            _p(
                "GigBid's core local product is implemented and reproducible: simulator, MCP servers, "
                "two durable graphs, RAG variants, verification, worker scheduling, safety controls, "
                "typed full-stack UI, live Render reviewer and evaluation gates. The evidence supports shipping the explicit "
                "hand-built graph, type-diverse V2 retrieval and Qwen3 4B writer while preserving "
                "negative results. The remaining human studies, external traces, recorded demo and "
                "instructor hidden run must still be filled with genuine evidence.",
                styles["body"],
            ),
            _p(
                "Primary evidence index: docs/REQUIREMENTS_MATRIX.md. Reproduction: make test; make "
                "eval; make eval-tools; make eval-model-profiles; make eval-agent-design; "
                "make eval-agent-model-design; make eval-portfolio-builder; "
                "pnpm --dir apps/web test:e2e.",
                styles["callout"],
            ),
        ]
    )

    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build())
