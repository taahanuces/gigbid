from fastapi.testclient import TestClient

from apps.simulator.main import app

AUTH = {"Authorization": "Bearer gigsim-development-token"}


def test_simulator_job_and_idempotent_proposal_flow() -> None:
    with TestClient(app) as client:
        jobs = client.get("/jobs", headers=AUTH, params={"tenant_id": "demo"})
        assert jobs.status_code == 200
        assert len(jobs.json()) == 100
        job = next(item for item in jobs.json() if not item["security_signals"])
        job_id = job["job_id"]

        preview = client.post(
            "/proposals/draft",
            headers=AUTH,
            json={
                "tenant_id": "demo",
                "job_id": job_id,
                "cover_letter": "A grounded public-data simulator proposal.",
                "dry_run": True,
            },
        )
        assert preview.status_code == 200
        assert preview.json()["tool_name"] == "create_proposal_draft"

        headers = {**AUTH, "Idempotency-Key": "draft-api-key-0001"}
        created = client.post(
            "/proposals/draft",
            headers=headers,
            json={
                "tenant_id": "demo",
                "job_id": job_id,
                "cover_letter": "A grounded public-data simulator proposal.",
                "dry_run": False,
            },
        )
        repeated = client.post(
            "/proposals/draft",
            headers=headers,
            json={
                "tenant_id": "demo",
                "job_id": job_id,
                "cover_letter": "A grounded public-data simulator proposal.",
                "dry_run": False,
            },
        )
        assert created.status_code == 200
        assert repeated.json() == created.json()

        proposal_id = created.json()["marketplace_id"]
        submitted = client.post(
            f"/proposals/{proposal_id}/submit",
            headers={**AUTH, "Idempotency-Key": "submit-api-key-0001"},
            json={"tenant_id": "demo"},
        )
        assert submitted.status_code == 200
        outcomes = client.get("/outcomes", headers=AUTH)
        assert outcomes.status_code == 200
        assert outcomes.json()[0]["data_origin"] == "synthetic_rule_based"


def test_simulator_requires_authentication() -> None:
    with TestClient(app) as client:
        assert client.get("/jobs", params={"tenant_id": "demo"}).status_code == 401
