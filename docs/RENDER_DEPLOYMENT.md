# Render Deployment

## Deployment profile

The assignment deployment uses GigSim as the only marketplace. Live Upwork access is neither required
nor configured. The Render Blueprint creates:

- `gigbid-web`: the Next.js reviewer UI on a free Render web service;
- `gigbid-api`: FastAPI and GigSim in one Docker service, with GigSim bound only to localhost;
- `gigbid-db`: free Render Postgres for durable LangGraph checkpoints and user state.

The deployment deliberately sets `MODEL_EXECUTION=deterministic` and `ASYNC_GRAPH_RUNS=false`. This
keeps the public demonstration inside free resources while retaining the same grounded proposal,
claim-verification, approval and idempotency boundaries. The separate local experiments remain the
evidence for Qwen/Llama routing and Celery reliability. Qdrant is not required by the in-memory V2
retriever used by the demo, and Redis is not required when graph runs execute synchronously.

## Live reviewer deployment

- Web: <https://gigbid-web.onrender.com>
- API health: <https://gigbid-api.onrender.com/health>
- Reviewer email: `reviewer@gigbid.local`
- Reviewer password: supplied out of band and stored only in Render; it is not committed.

On 12 November 2026 the public health endpoint returned `status=ok`,
`marketplace=available`, and `checkpointer=postgres`. A clean reviewer login loaded 100 GigSim jobs,
and a hosted analysis produced a five-event run with five durable checkpoints. The same run rendered
successfully at a 390 by 844 mobile viewport. Exact service, deploy, commit, run and trace identifiers
are retained in `docs/DEPLOYMENT_EVIDENCE.md`.

## Deploy

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render discovers the root `render.yaml`.
4. Supply a strong `REVIEWER_PASSWORD` when prompted. Do not commit it.
5. Apply the Blueprint and wait for Postgres, API and web deployments to become live.
6. Verify the API `/health` response and sign in through the web URL with
   `reviewer@gigbid.local` and the password supplied in step 4.

`NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` are wired from Render-assigned external URLs, so no hostname
is hardcoded. Render generates the application and GigSim secrets, and Postgres is accessible only on
Render's private network.

## Verification

Run the following against the assigned URLs:

```bash
curl --fail --show-error "$GIGBID_API_URL/health"
curl --fail --show-error "$GIGBID_WEB_URL/login"
```

Then exercise login, ranked inbox, job analysis, cited proposal, approval, pipeline and analytics from
a clean browser. The deployment is successful only when API health is `ok` and the browser flow uses
the live API rather than fixture interception.

## Free-tier limitations

Render free web services spin down after inactivity, so the first request can be slow. Free Postgres
is limited to 1 GB, has no backups, and expires after 30 days. This profile is suitable for assignment
review, not real production data. Upgrade or recreate the database before the review window expires.
