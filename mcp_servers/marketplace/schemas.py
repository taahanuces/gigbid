from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.handoffs import DryRunPreview, MarketplaceReceipt


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    trace_id: str = Field(min_length=8, max_length=128)


class SearchJobsInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    query: str = Field(default="", max_length=500)


class GetJobInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)


class ClientHistoryInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)


class ConnectsInput(ToolInput):
    tenant_id: str = Field(min_length=1)


class MessagesInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)


class ProposalDraftInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    cover_letter: str = Field(min_length=20, max_length=5000)
    screening_answers: dict[str, str] = Field(default_factory=dict)
    connects_cost: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    dry_run: bool = True


class SubmitProposalInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=200)
    dry_run: bool = True


class SendMessageInput(ToolInput):
    tenant_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    body: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=8, max_length=200)
    dry_run: bool = True


class ProposalActionResult(BaseModel):
    preview: DryRunPreview | None = None
    receipt: MarketplaceReceipt | None = None

    @model_validator(mode="after")
    def exactly_one_result(self) -> ProposalActionResult:
        if (self.preview is None) == (self.receipt is None):
            raise ValueError("exactly one of preview or receipt is required")
        return self


class ConnectsResult(BaseModel):
    balance: int = Field(ge=0)


class JobSearchResult(BaseModel):
    jobs: list[dict[str, object]]


class MessagesResult(BaseModel):
    messages: list[dict[str, object]]
