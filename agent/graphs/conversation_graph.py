from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypeAlias, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from agent.handoffs import ApprovalAction, ApprovalDecision
from agent.marketplace_port import MarketplacePort
from agent.nodes.client_liaison import LiaisonDraft, draft_client_reply
from agent.persistence import checkpoint_serializer
from agent.security import EMAIL_PATTERN, PHONE_PATTERN, find_injected_instructions


class ConversationState(TypedDict, total=False):
    thread_id: str
    tenant_id: str
    user_id: str
    conversation_id: str
    inbound_message: str
    free_slots: list[str]
    draft: LiaisonDraft
    approval: ApprovalDecision
    idempotency_key: str
    receipt: dict[str, Any]
    status: str
    step_count: Annotated[int, operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]


ConversationCompiledGraph: TypeAlias = CompiledStateGraph[
    ConversationState, None, ConversationState, ConversationState
]


def build_conversation_graph(
    marketplace: MarketplacePort,
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    store: BaseStore | None = None,
    max_steps: int = 12,
) -> ConversationCompiledGraph:
    def budget_exhausted(state: ConversationState) -> bool:
        return state.get("step_count", 0) >= max_steps

    def liaison(state: ConversationState) -> dict[str, object]:
        draft = draft_client_reply(state["inbound_message"], state.get("free_slots"))
        return {
            "draft": draft,
            "status": "blocked" if draft.risk_signals else "drafted",
            "step_count": 1,
            "events": [{"node": "client_liaison", "intent": draft.intent}],
        }

    def liaison_route(state: ConversationState) -> Literal["prepare_approval", "done"]:
        return "done" if state["draft"].risk_signals else "prepare_approval"

    def prepare_approval(state: ConversationState) -> dict[str, object]:
        return {
            "idempotency_key": state.get("idempotency_key")
            or (f"message:{state['tenant_id']}:{state['conversation_id']}:{state['thread_id']}"),
            "status": "awaiting_approval",
            "step_count": 1,
            "events": [{"node": "prepare_approval", "status": "complete"}],
        }

    def approval(state: ConversationState) -> dict[str, object]:
        response = interrupt(
            {
                "thread_id": state["thread_id"],
                "conversation_id": state["conversation_id"],
                "draft": state["draft"].model_dump(mode="json"),
            }
        )
        decision = ApprovalDecision.model_validate(response)
        updates: dict[str, object] = {
            "approval": decision,
            "status": decision.action.value,
            "step_count": 1,
            "events": [{"node": "approval", "status": decision.action.value}],
        }
        if decision.action == ApprovalAction.EDIT:
            updates["draft"] = state["draft"].model_copy(
                update={"reply": decision.edited_cover_letter or ""}
            )
        return updates

    def approval_route(
        state: ConversationState,
    ) -> Literal["send", "safety", "done", "attention"]:
        if budget_exhausted(state):
            return "attention"
        action = state["approval"].action
        if action == ApprovalAction.APPROVE:
            return "send"
        if action == ApprovalAction.EDIT:
            return "safety"
        return "done"

    def safety(state: ConversationState) -> dict[str, object]:
        reply = state["draft"].reply
        injected = find_injected_instructions(reply)
        sanitized = EMAIL_PATTERN.sub("[removed]", reply)
        sanitized = PHONE_PATTERN.sub("[removed]", sanitized)
        signals = list(injected)
        if sanitized != reply:
            signals.append("off-platform contact removed from edited reply")
        draft = state["draft"].model_copy(update={"reply": sanitized, "risk_signals": injected})
        return {
            "draft": draft,
            "status": "blocked" if injected else "awaiting_approval",
            "step_count": 1,
            "events": [{"node": "message_safety", "signals": signals}],
        }

    def safety_route(state: ConversationState) -> Literal["approval", "done", "attention"]:
        if budget_exhausted(state):
            return "attention"
        return "done" if state["draft"].risk_signals else "approval"

    async def send(state: ConversationState) -> dict[str, object]:
        receipt = await marketplace.send_message(
            tenant_id=state["tenant_id"],
            conversation_id=state["conversation_id"],
            body=state["draft"].reply,
            idempotency_key=state["idempotency_key"],
        )
        return {
            "receipt": receipt.model_dump(mode="json"),
            "status": receipt.status,
            "step_count": 1,
            "events": [{"node": "send", "status": receipt.status}],
        }

    def needs_attention(state: ConversationState) -> dict[str, object]:
        return {
            "status": "needs_attention",
            "step_count": 1,
            "events": [{"node": "needs_attention", "status": "budget_exhausted"}],
        }

    builder = StateGraph(ConversationState)
    builder.add_node("liaison", liaison)
    builder.add_node("prepare_approval", prepare_approval)
    builder.add_node("approval", approval)
    builder.add_node("safety", safety)
    builder.add_node("send", send)
    builder.add_node("needs_attention", needs_attention)
    builder.add_edge(START, "liaison")
    builder.add_conditional_edges(
        "liaison",
        liaison_route,
        {"prepare_approval": "prepare_approval", "done": END},
    )
    builder.add_edge("prepare_approval", "approval")
    builder.add_conditional_edges(
        "approval",
        approval_route,
        {
            "send": "send",
            "safety": "safety",
            "done": END,
            "attention": "needs_attention",
        },
    )
    builder.add_conditional_edges(
        "safety",
        safety_route,
        {"approval": "approval", "done": END, "attention": "needs_attention"},
    )
    builder.add_edge("send", END)
    builder.add_edge("needs_attention", END)
    active_checkpointer = checkpointer or InMemorySaver(serde=checkpoint_serializer(LiaisonDraft))
    return builder.compile(checkpointer=active_checkpointer, store=store)
