from fastapi.testclient import TestClient

from apps.api.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "reviewer@gigbid.local", "password": "GigBidDemo2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_vertical_slice() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        headers["X-Trace-ID"] = "trace-test-4016"
        jobs = client.get("/api/jobs", headers=headers)
        assert jobs.status_code == 200
        assert len(jobs.json()) == 2
        run = client.post(
            "/api/jobs/job-forecast-001/analyze",
            headers=headers,
            json={"user_floor": 300},
        )
        assert run.status_code == 200
        assert run.json()["status"] == "awaiting_approval"
        assert run.headers["X-Trace-ID"] == "trace-test-4016"
        assert run.json()["trace_id"] == "trace-test-4016"
        assert run.json()["state"]["trace_id"] == "trace-test-4016"
        assert run.json()["trace_url"] is None
        thread_id = run.json()["thread_id"]
        inbox = client.get("/api/jobs/ranked/inbox", headers=headers)
        assert inbox.status_code == 200
        analysed = next(item for item in inbox.json() if item["job_id"] == "job-forecast-001")
        assert analysed["action"] == "bid"
        assert analysed["fit_score"] is not None
        assert analysed["thread_id"] == thread_id
        events = client.get(f"/api/runs/{thread_id}/events", headers=headers)
        assert events.status_code == 200
        assert events.headers["content-type"].startswith("text/event-stream")
        assert "event: node" in events.text
        assert "event: status" in events.text
        assert "awaiting_approval" in events.text
        regenerated = client.post(
            f"/api/runs/{thread_id}/regenerate-paragraph",
            headers=headers,
            json={"paragraph_index": 1},
        )
        assert regenerated.status_code == 200
        assert regenerated.json()["paragraph_index"] == 1
        assert "[" in regenerated.json()["replacement"]
        assert "verified_evidence_only" in regenerated.json()["reasons"]
        history = client.get(f"/api/runs/{thread_id}/history", headers=headers)
        assert history.status_code == 200
        checkpoints = history.json()["checkpoints"]
        assert len(checkpoints) >= 2
        replay = client.get(
            f"/api/runs/{thread_id}/replay/{checkpoints[0]['checkpoint_id']}",
            headers=headers,
        )
        assert replay.status_code == 200
        assert replay.json()["read_only"] is True
        assert replay.json()["thread_id"] == thread_id
        approved = client.post(
            f"/api/runs/{thread_id}/approval",
            headers=headers,
            json={"action": "approve"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "draft_created"

        pipeline = client.get("/api/pipeline", headers=headers)
        assert pipeline.status_code == 200
        assert len(pipeline.json()["cards"]) == 1
        assert pipeline.json()["cards"][0]["status"] == "drafted"

        analytics = client.get("/api/analytics", headers=headers)
        assert analytics.status_code == 200
        assert set(analytics.json()["personas"]) == {
            "ai-ml-engineer",
            "full-stack-developer",
            "data-analyst",
        }
        assert "v2_hybrid" in analytics.json()["rag_variants"]
        assert analytics.json()["connects_spent"] > 0
        assert analytics.json()["categories"]
        assert analytics.json()["top_rejection_reasons"]["prompt_injection"] > 0

        messages = client.get("/api/messages", headers=headers)
        assert messages.status_code == 200
        assert messages.json() == {"threads": []}

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "gigbid_api_requests_total" in metrics.text
        assert "gigbid_graph_runs_total" in metrics.text


def test_invalid_incoming_trace_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Trace-ID": "bad trace id"})
        trace_id = response.headers["X-Trace-ID"]
        assert response.status_code == 200
        assert trace_id != "bad trace id"
        assert len(trace_id) == 32


def test_memory_outcome_promotion_and_deletion() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        last = None
        for index in range(5):
            last = client.post(
                "/api/memories/outcomes",
                headers=headers,
                json={
                    "job_id": f"job-outcome-{index}",
                    "category": "data",
                    "strategy": "lead-with-metric",
                    "replied": index < 3,
                    "hired": False,
                },
            )
            assert last.status_code == 200
        assert last is not None
        promoted = last.json()["promoted"]
        assert promoted["value"] == "lead-with-metric"

        memories = client.get("/api/memories", headers=headers)
        assert memories.status_code == 200
        assert len(memories.json()) == 1
        deleted = client.delete(
            f"/api/memories/outcome/{promoted['key']}",
            headers=headers,
        )
        assert deleted.status_code == 204
        assert client.get("/api/memories", headers=headers).json() == []


def test_conversation_api_requires_approval_before_message_write() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        drafted = client.post(
            "/api/conversations/conversation-api-1/draft",
            headers=headers,
            json={
                "inbound_message": "Can we schedule an interview call?",
                "free_slots": ["2026-11-12T10:00:00+05:00"],
            },
        )
        assert drafted.status_code == 200
        assert drafted.json()["status"] == "awaiting_approval"
        assert drafted.json()["state"]["draft"]["intent"] == "interview"
        thread_id = drafted.json()["thread_id"]

        approved = client.post(
            f"/api/conversations/runs/{thread_id}/approval",
            headers=headers,
            json={"action": "approve"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "sent"

        messages = client.get("/api/messages", headers=headers)
        assert messages.status_code == 200
        assert len(messages.json()["threads"]) == 1
        assert messages.json()["threads"][0]["messages"][0]["direction"] == "outbound"


def test_profile_persists_boundaries_and_selects_persona_index() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        initial = client.get("/api/profile", headers=headers)
        assert initial.status_code == 200
        assert initial.json()["settings"]["persona"] == "data-analyst"
        assert initial.json()["evidence_count"] > 0

        settings = {
            **initial.json()["settings"],
            "persona": "full-stack-developer",
            "fixed_price_floor": 725,
            "search_keywords": [" Next.js ", "PostgreSQL", "Next.js"],
            "onboarding_complete": True,
        }
        updated = client.put("/api/profile", headers=headers, json=settings)
        assert updated.status_code == 200
        assert updated.json()["settings"]["fixed_price_floor"] == 725
        assert updated.json()["settings"]["search_keywords"] == ["next.js", "postgresql"]
        assert updated.json()["data_origin"] == "synthetic persona portfolio; public jobs"

        run = client.post(
            "/api/jobs/job-forecast-001/analyze",
            headers=headers,
            json={},
        )
        assert run.status_code == 200
        state = run.json()["state"]
        assert state["persona"] == "full-stack-developer"
        assert state["user_floor"] == 725
        assert state["evidence"]
        assert all(
            item["evidence_id"].startswith("full-stack-developer:")
            for item in state["evidence"]
        )


def test_portfolio_upload_is_incrementally_indexed_and_deletable() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        uploaded = client.post(
            "/api/portfolio/upload",
            headers=headers,
            data={"persona": "data-analyst", "skills": "SQL, dbt"},
            files={
                "file": (
                    "warehouse.md",
                    b"# Warehouse quality\nBuilt tested SQL and dbt models for analytics.",
                    "text/markdown",
                )
            },
        )
        assert uploaded.status_code == 200
        assert len(uploaded.json()) == 1
        item = uploaded.json()[0]
        assert item["data_origin"] == "private_user_data_not_committed"
        assert item["skills"] == ["SQL", "dbt"]

        listed = client.get("/api/portfolio", headers=headers)
        assert listed.status_code == 200
        assert [record["evidence_id"] for record in listed.json()] == [item["evidence_id"]]

        run = client.post(
            "/api/jobs/job-forecast-001/analyze",
            headers=headers,
            json={},
        )
        assert run.status_code == 200
        portfolio_ids = {
            record["evidence_id"] for record in run.json()["state"]["portfolio_evidence"]
        }
        assert item["evidence_id"] in portfolio_ids

        deleted = client.delete(f"/api/portfolio/{item['evidence_id']}", headers=headers)
        assert deleted.status_code == 204
        assert client.get("/api/portfolio", headers=headers).json() == []
