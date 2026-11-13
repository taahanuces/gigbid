# Deployment Evidence

## Public endpoints

- Reviewer UI: <https://gigbid-web.onrender.com>
- API health: <https://gigbid-api.onrender.com/health>
- Public trace index: <https://gigbid-web.onrender.com/traces>
- Scam/injection skip: <https://gigbid-web.onrender.com/traces/scam-injection-skip>
- Critic loop and approval: <https://gigbid-web.onrender.com/traces/approved-critic-loop>
- Crash/resume exactly-once: <https://gigbid-web.onrender.com/traces/crash-resume-exactly-once>
- Reviewer email: `reviewer@gigbid.local`
- Reviewer password: supplied out of band; never committed or included in this document.

## Render resources

| Resource | Render identifier | Verified state |
| --- | --- | --- |
| Blueprint | `exs-dbqvnhuk1f9s73as960g` | Synced |
| Web service | `srv-dbqvotkipgvc73cv2oh0` | Live |
| API service | `srv-dbqvotcipgvc73cv2n90` | Live |
| Postgres | `dpg-dboctkipgvc73cv12q0-a` | Available to the API on Render's private network |
| Web deploy | `dep-dbqvotsipgvc73cv2p50` | Succeeded |
| API deploy | `dep-dbqvotkipgvc73cv2o00` | Succeeded |

The initial deployed source was commit `f3f95f387daa97e5eb448764789e25a232fd668a`; Render then
auto-deployed the versioned public-evidence update from `main`. The password is stored as a Render
secret and is deliberately absent from Git, logs, screenshots and report artifacts.

## Hosted verification — 12 November 2026

The public `/health` response was:

```json
{
  "status": "ok",
  "service": "gigbid-api",
  "dependencies": {
    "marketplace": "available",
    "checkpointer": "postgres"
  }
}
```

The reviewer login loaded 100 real public-data-derived GigSim jobs. The hosted graph then analyzed
`job-c76b8b9861a23dc6f71359be` and produced:

- thread `6e1b2e0a-783b-453a-b78e-d7de1a6eba91`;
- trace `6d3770a62d3041e99151e8821c894723`;
- five events: Load Job, Analyst, Fit Matcher, Risk Assessor and Decision;
- a safe `skip` decision with no marketplace write;
- five durable checkpoints visible in the replay UI.

The same public run rendered successfully in a clean signed-in browser at the default desktop size and
at a 390 by 844 mobile viewport. Render application logs independently recorded the analysis POST as
HTTP 200 and the subsequent run, event and history reads as HTTP 200.

## Scope and limitations

This deployment demonstrates the assignment workflow with GigSim only. It intentionally does not use
an Upwork account or perform a live marketplace write. The free reviewer profile uses deterministic
model execution and synchronous graph runs, while the two-model and Celery evidence remains in the
reproducible local experiments. Phoenix is verified locally. The three public URLs are deliberately
small, signed-out trace snapshots regenerated from the real graph and fault-injection harness; they
preserve redacted events, checkpoint/write counts and source references without exposing prompts,
credentials, PII or private portfolio text. Render free services may cold-start after inactivity, and
free Postgres has the limits documented in `docs/RENDER_DEPLOYMENT.md`.
