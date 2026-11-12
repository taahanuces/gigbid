from __future__ import annotations

import importlib
from pathlib import Path

import yaml
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_is_free_simulator_only_deployment() -> None:
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in blueprint["services"]}

    assert set(services) == {"gigbid-api", "gigbid-web"}
    assert all(service["plan"] == "free" for service in services.values())
    assert blueprint["databases"][0]["plan"] == "free"

    api_environment = {
        item["key"]: item
        for item in services["gigbid-api"]["envVars"]
        if "key" in item
    }
    assert api_environment["MARKETPLACE_MODE"]["value"] == "gigsim"
    assert api_environment["MODEL_EXECUTION"]["value"] == "deterministic"
    assert api_environment["ASYNC_GRAPH_RUNS"]["value"] == "false"
    assert not any(key.startswith("UPWORK_") for key in api_environment)


def test_production_cors_requires_explicit_render_origin(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    main = importlib.import_module("apps.api.main")

    assert main._cors_origins() == []

    monkeypatch.setenv("CORS_ORIGINS", "https://gigbid-web.onrender.com/")
    assert main._cors_origins() == ["https://gigbid-web.onrender.com"]
