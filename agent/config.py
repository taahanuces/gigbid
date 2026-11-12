from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarketplaceConfig(StrictConfig):
    mode: str
    max_requests_per_minute: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    saved_search_interval_minutes: int = Field(ge=60)


class BudgetConfig(StrictConfig):
    max_graph_steps: int = Field(gt=0)
    max_revisions: int = Field(ge=0, le=2)
    max_tokens_per_job: int = Field(gt=0)
    max_cost_per_job_usd: float = Field(ge=0)
    max_cost_per_proposal_usd: float = Field(ge=0)
    target_p95_job_latency_seconds: float = Field(gt=0)
    target_p95_proposal_latency_seconds: float = Field(gt=0)


class ThresholdConfig(StrictConfig):
    minimum_fit_score: float = Field(ge=0, le=1)
    maximum_risk_score: float = Field(ge=0, le=1)
    auto_skip_fit_score: float = Field(ge=0, le=1)
    minimum_evidence_score: float = Field(ge=0, le=1)
    maximum_connects_per_bid: int = Field(ge=0)


class RagConfig(StrictConfig):
    variant: str
    top_k: int = Field(gt=0)
    chunk_size: int = Field(gt=0)
    chunk_overlap: int = Field(ge=0)


class MemoryConfig(StrictConfig):
    style_minimum_consistent_edits: int = Field(gt=1)
    outcome_minimum_observations: int = Field(gt=0)
    outcome_minimum_reply_rate: float = Field(ge=0, le=1)


class PolicyConfig(StrictConfig):
    rules_file: str
    block_off_platform_contact: bool
    block_unpaid_production_work: bool
    block_guarantees: bool
    require_claim_evidence: bool


class AppConfig(StrictConfig):
    marketplace: MarketplaceConfig
    models: dict[str, Any]
    budgets: BudgetConfig
    thresholds: ThresholdConfig
    rag: RagConfig
    memory: MemoryConfig
    policy: PolicyConfig


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value)
    return value


@lru_cache(maxsize=4)
def load_config(path: str | Path = "agent/config.yaml") -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(_expand_env(raw))
