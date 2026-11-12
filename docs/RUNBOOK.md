# Runbook

## Startup

Use `make dev` for the complete Compose stack or `make api` for the API alone. Health endpoints must
report dependencies separately so the UI can distinguish degraded mode from total failure.

## Marketplace outage

The GigSim adapter performs three bounded network retries with exponential backoff. Celery analysis
tasks retry connection and timeout failures three times; a terminal task failure is written to the
bounded, PII-redacted Redis list configured by `DEAD_LETTER_KEY`. Marketplace writes retain the
approval and idempotency key, and the UI never reports a write as successful without an adapter
receipt.

Inspect the queue with
`docker compose -f infra/docker-compose.yml exec redis redis-cli LRANGE gigbid:dead-letter 0 20`.
Entries expire after `DEAD_LETTER_RETENTION_SECONDS` and the list is trimmed to `DEAD_LETTER_MAX`.
Review the failure and upstream state before replaying work; do not blindly re-run a marketplace
write. Job enqueue uses one Redis Lua operation for the deduplication lock and event publish, so a
retry cannot leave a lock without its corresponding event.

## Crash during approval

Approval interrupts are checkpointed in Postgres. After restart, the API resumes the same graph thread.
The write uses the stored idempotency key, making retries safe.

Run `make test-postgres` after starting the Compose Postgres service to exercise a real connection
shutdown/reopen between approval and resume. CI runs the same test against a fresh Postgres 17 service.
The deterministic in-memory suite separately simulates a crash after the upstream marketplace accepts
the write but before the graph checkpoints the receipt; retrying reuses the saved idempotency key and
does not create a second proposal.

## Tracing and metrics

Every HTTP request receives an `X-Trace-ID`. The same ID is checkpointed in graph state, returned in
run responses, included in marketplace audit events and propagated by worker job events. `/metrics`
exposes bounded-label Prometheus request and graph latency/counter series. When `TRACE_LOG_PATH` is
set, the API also writes PII-redacted JSONL request spans; the Compose API mounts these at
`/data/traces`.

Compose includes a pinned self-hosted Phoenix instance at `http://localhost:6006`. The API and worker
export content-free OTLP/HTTP spans for HTTP requests, bid/conversation graph executions, resumes and
model calls; identifiers are redacted and model prompts, portfolio text and proposal bodies are not
span attributes. `TRACE_VIEWER_URL_TEMPLATE` controls the run-screen link and
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` controls export. The local instance deliberately disables auth
for loopback development only. Enable Phoenix auth, create a scoped key, set `PHOENIX_API_KEY`, use
TLS and replace the viewer URL before exposing it publicly.

## Worker limits

Workers acknowledge tasks after completion, prefetch one task, cancel long-running tasks after broker
connection loss, apply a 120-second soft limit and a 150-second hard limit, and use a one-hour Redis
visibility timeout. These limits are defaults for the deterministic scaffold and should be tuned using
production latency distributions.

`ASYNC_GRAPH_RUNS=true` seeds a Postgres start checkpoint in the API and returns the queued thread
immediately. The Celery worker verifies tenant, user and job identity against that checkpoint, resumes
the graph, and publishes completion on `gigbid:runs`. Beat executes each saved search every four hours;
the tenant-scoped seen-job store prevents repeat queueing. The run UI reads intermediate checkpoints
over authenticated SSE.

The Compose `ollama-init` service pulls the measured Qwen3 4B primary and Llama 3.1 8B fallback once
into the named volume. Writer calls try the node-routed Qwen model, then Llama; a model outage is
recorded in run state and uses the conservative deterministic writer so approval and grounding remain
available.

## Live polling

Saved searches default to every four hours. Live intervals remain configurable and must respect the
official provider's limits. No scraping, browser automation, or session cookies are permitted.

