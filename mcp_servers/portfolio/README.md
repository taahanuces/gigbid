# GigBid Portfolio MCP

The Portfolio MCP server exposes tenant-scoped, read-only portfolio evidence for grounded proposal
generation. It is an independently implemented MCP server, not a wrapper around the starter kit. The
repository includes a runnable service and container; public package publication is a separate
submission action because it requires the student's registry/account.

## Tools and resources

| Surface | Purpose | Effect |
| --- | --- | --- |
| `search_evidence(requirement, k, filters)` | Retrieve the strongest evidence for one requirement | Read-only |
| `get_case_study(evidence_id)` | Load one complete case study | Read-only |
| `list_skills()` | List skills in the scoped corpus | Read-only |
| `portfolio://case/{evidence_id}` | Case-study JSON resource | Read-only |
| `portfolio://proposal/{evidence_id}` | Historical-proposal JSON resource | Read-only |
| `answer_screening_question(question)` | Evidence-first prompt template | Read-only |

All tools declare read-only, non-destructive, idempotent, closed-world annotations. Arguments and
outputs use strict Pydantic models.

## Evidence input

The default development server loads all `data/processed/personas/*.jsonl` files and scopes them to
tenant `demo`. Those files are explicitly synthetic. To use private local evidence, provide a
comma-separated list of JSONL files and a tenant/persona scope:

```bash
export PORTFOLIO_DATA_PATHS=/absolute/path/portfolio.jsonl
export PORTFOLIO_TENANT_ID=my-tenant
export PORTFOLIO_PERSONA=full-stack-developer
```

Each non-empty line must validate as `agent.handoffs.EvidenceItem`. The loader reports the exact file
and line on invalid input and fails closed on missing files. Private evidence paths and uploads must
not be committed.

## Run locally

From the GigBid repository root:

```bash
python -m pip install -e ".[dev]"
export MCP_BEARER_TOKEN=replace-with-a-long-random-local-token
python -m mcp_servers.portfolio.server
```

The streamable HTTP endpoint is `http://127.0.0.1:8101/mcp`. Clients send
`Authorization: Bearer <token>`. If `MCP_BEARER_TOKEN` is absent, authentication is disabled only to
support in-process tests; a deployed service must set it. Host, port, and resource URL can be changed
with `MCP_HOST`, `MCP_PORT`, and `MCP_RESOURCE_URL`.

Run the packaged service with the full local stack:

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml up --build portfolio-mcp
```

The MCP image includes the generated synthetic persona corpus, so its default search surface is not
empty. Override `PORTFOLIO_DATA_PATHS` with a mounted private file for non-demo use.

## Verify

```bash
pytest tests/integration/test_mcp_inmemory.py tests/contract/test_mcp_schemas.py \
  tests/unit/test_portfolio_service.py -q
```

For manual inspection, connect an MCP Inspector-compatible client to the streamable HTTP URL and
supply the bearer header. Capture the advertised tool schemas and at least one `search_evidence` call
for submission evidence. Do not include a private evidence body or bearer token in screenshots.

## Publish for the assignment

1. Freeze and tag the exact tested commit.
2. Build the `infra/docker/mcp.Dockerfile` image and scan it for secrets.
3. Push the versioned image or package through the instructor-approved registry/channel.
4. Deploy behind TLS with a unique bearer secret and a non-public evidence store.
5. Verify the public MCP endpoint from a clean client and record the install URL and version in
   `docs/SUBMISSION_CHECKLIST.md`.
6. Revoke temporary credentials after the review.

Publication is intentionally not claimed by this repository. A genuine public endpoint and registry
URL require account ownership and must be added by the student.

## Trust boundary

The server never writes to GitHub, Upwork, or a workspace. It returns only evidence already present in
its scoped corpus. Proposal generation and final claim verification remain downstream responsibilities;
retrieval relevance alone does not prove that a claim is supported.
