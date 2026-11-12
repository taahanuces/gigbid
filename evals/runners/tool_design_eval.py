from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

ROOT = Path(__file__).resolve().parents[2]
DESIGNS = ("fine_grained", "coarse_grained", "best_descriptions")


class ToolTask(TypedDict):
    task_id: str
    instruction: str
    expected_tool: str
    expected_args: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolTaskResult:
    task_id: str
    design: str
    expected_tool: str
    selected_tool: str | None
    selected_arguments: dict[str, object]
    correct_tool: bool
    correct_arguments: bool
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    error: str | None = None

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


TOOL_SERVERS = {
    "search_evidence": "portfolio",
    "get_case_study": "portfolio",
    "list_skills": "portfolio",
    "search_jobs": "marketplace",
    "get_job": "marketplace",
    "get_client_history": "marketplace",
    "get_connects_balance": "marketplace",
    "list_messages": "marketplace",
    "create_proposal_draft": "marketplace",
    "submit_proposal": "marketplace",
    "send_message": "marketplace",
    "list_free_slots": "workspace",
    "create_tentative_hold": "workspace",
    "create_email_draft": "workspace",
}

DESCRIPTIONS = {
    "search_evidence": "Find verified portfolio evidence relevant to one job requirement.",
    "get_case_study": "Load one full case study by evidence ID.",
    "list_skills": "List skills appearing in verified portfolio evidence.",
    "search_jobs": "Search marketplace jobs through the configured adapter.",
    "get_job": "Load a complete marketplace job.",
    "get_client_history": "Load marketplace history used for client-risk analysis.",
    "get_connects_balance": "Return the current Connects balance.",
    "list_messages": "List messages in one marketplace conversation.",
    "create_proposal_draft": "Preview or create one proposal draft after approval.",
    "submit_proposal": "Preview or submit a simulator proposal.",
    "send_message": "Preview or send an approved marketplace message.",
    "list_free_slots": "Return available interview slots in an explicit time range.",
    "create_tentative_hold": "Preview or create an idempotent tentative calendar hold.",
    "create_email_draft": "Preview or create an email draft; it never sends mail.",
}

BEST_GUIDANCE = {
    "search_evidence": (
        "Use for semantic portfolio search; do not use when an evidence ID is known."
    ),
    "get_case_study": "Use only when a specific evidence ID is known; do not use for search.",
    "list_skills": "Use only to inventory portfolio skills; it returns no case-study detail.",
    "search_jobs": "Use for discovery by query; do not use when an exact job ID is supplied.",
    "get_job": "Use only for one known job ID; do not use for discovery.",
    "get_client_history": "Use for client reputation and payment history, never job details.",
    "get_connects_balance": "Use only for the tenant's current Connects balance.",
    "list_messages": "Use only to read an existing conversation; this never sends a message.",
    "create_proposal_draft": "Use for proposal draft preview/creation, not final submission.",
    "submit_proposal": "Use only for a known proposal ID; keep dry_run true during planning.",
    "send_message": "Use for a conversation reply; keep dry_run true until human approval.",
    "list_free_slots": "Use to read availability; do not create a hold with this tool.",
    "create_tentative_hold": "Use for a calendar hold, not merely checking availability.",
    "create_email_draft": "Use for an email draft only; it cannot send the email.",
}


def string_schema() -> dict[str, object]:
    return {"type": "string"}


def integer_schema() -> dict[str, object]:
    return {"type": "integer"}


ARGUMENT_FIELDS: dict[str, dict[str, dict[str, object]]] = {
    "search_evidence": {"requirement": string_schema(), "k": integer_schema()},
    "get_case_study": {"evidence_id": string_schema()},
    "list_skills": {},
    "search_jobs": {
        "tenant_id": string_schema(),
        "query": string_schema(),
        "trace_id": string_schema(),
    },
    "get_job": {
        "tenant_id": string_schema(),
        "job_id": string_schema(),
        "trace_id": string_schema(),
    },
    "get_client_history": {
        "tenant_id": string_schema(),
        "client_id": string_schema(),
        "trace_id": string_schema(),
    },
    "get_connects_balance": {"tenant_id": string_schema(), "trace_id": string_schema()},
    "list_messages": {
        "tenant_id": string_schema(),
        "conversation_id": string_schema(),
        "trace_id": string_schema(),
    },
    "create_proposal_draft": {
        "tenant_id": string_schema(),
        "job_id": string_schema(),
        "cover_letter": string_schema(),
        "connects_cost": integer_schema(),
        "idempotency_key": string_schema(),
        "dry_run": {"type": "boolean"},
        "trace_id": string_schema(),
    },
    "submit_proposal": {
        "tenant_id": string_schema(),
        "proposal_id": string_schema(),
        "idempotency_key": string_schema(),
        "dry_run": {"type": "boolean"},
        "trace_id": string_schema(),
    },
    "send_message": {
        "tenant_id": string_schema(),
        "conversation_id": string_schema(),
        "body": string_schema(),
        "idempotency_key": string_schema(),
        "dry_run": {"type": "boolean"},
        "trace_id": string_schema(),
    },
    "list_free_slots": {
        "tenant_id": string_schema(),
        "start": string_schema(),
        "end": string_schema(),
        "timezone": string_schema(),
        "limit": integer_schema(),
    },
    "create_tentative_hold": {
        "tenant_id": string_schema(),
        "starts_at": string_schema(),
        "ends_at": string_schema(),
        "title": string_schema(),
        "idempotency_key": string_schema(),
        "dry_run": {"type": "boolean"},
    },
    "create_email_draft": {
        "tenant_id": string_schema(),
        "recipient": string_schema(),
        "subject": string_schema(),
        "body": string_schema(),
        "idempotency_key": string_schema(),
        "dry_run": {"type": "boolean"},
    },
}


def fine_tools(*, best: bool) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for name, fields in ARGUMENT_FIELDS.items():
        description = DESCRIPTIONS[name]
        if best:
            description = f"{description} {BEST_GUIDANCE[name]}"
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": fields,
                        "required": list(fields),
                        "additionalProperties": False,
                    },
                },
            }
        )
    return tools


def coarse_tools() -> list[dict[str, object]]:
    by_server: dict[str, list[str]] = {}
    for tool, server in TOOL_SERVERS.items():
        by_server.setdefault(server, []).append(tool)
    return [
        {
            "type": "function",
            "function": {
                "name": f"{server}_action",
                "description": f"Perform any {server} operation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": sorted(operations)},
                        "arguments": {"type": "object"},
                    },
                    "required": ["operation", "arguments"],
                    "additionalProperties": False,
                },
            },
        }
        for server, operations in by_server.items()
    ]


def tools_for(design: str) -> list[dict[str, object]]:
    if design == "fine_grained":
        return fine_tools(best=False)
    if design == "best_descriptions":
        return fine_tools(best=True)
    if design == "coarse_grained":
        return coarse_tools()
    raise ValueError(f"Unknown design: {design}")


def load_tasks(path: Path | None = None) -> list[ToolTask]:
    source = path or ROOT / "evals/datasets/tool_design_tasks.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Tool task dataset must be a list")
    tasks = cast(list[ToolTask], raw)
    if len(tasks) != 40:
        raise ValueError(f"Expected exactly 40 tool tasks, found {len(tasks)}")
    return tasks


def expected_selection(task: ToolTask, design: str) -> tuple[str, dict[str, object]]:
    if design != "coarse_grained":
        return task["expected_tool"], task["expected_args"]
    server = TOOL_SERVERS[task["expected_tool"]]
    return f"{server}_action", {
        "operation": task["expected_tool"],
        "arguments": task["expected_args"],
    }


def arguments_match(actual: dict[str, object], expected: dict[str, object]) -> bool:
    return actual == expected


def parse_tool_call(response: dict[str, Any]) -> tuple[str | None, dict[str, object]]:
    message = response.get("message")
    if not isinstance(message, dict):
        return None, {}
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        return None, {}
    function = calls[0].get("function")
    if not isinstance(function, dict):
        return None, {}
    name = function.get("name")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    return (str(name) if name else None), (
        cast(dict[str, object], arguments) if isinstance(arguments, dict) else {}
    )


def run_task(
    client: httpx.Client,
    *,
    model: str,
    design: str,
    task: ToolTask,
) -> ToolTaskResult:
    expected_tool, expected_args = expected_selection(task, design)
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "Select exactly one tool. Copy all explicit argument values exactly.",
            },
            {"role": "user", "content": task["instruction"]},
        ],
        "tools": tools_for(design),
        "options": {"temperature": 0, "seed": 4016},
    }
    started = time.perf_counter()
    try:
        response = client.post("/api/chat", json=payload)
        response.raise_for_status()
        body = cast(dict[str, Any], response.json())
        selected_tool, selected_args = parse_tool_call(body)
        return ToolTaskResult(
            task_id=task["task_id"],
            design=design,
            expected_tool=expected_tool,
            selected_tool=selected_tool,
            selected_arguments=selected_args,
            correct_tool=selected_tool == expected_tool,
            correct_arguments=(
                selected_tool == expected_tool and arguments_match(selected_args, expected_args)
            ),
            prompt_tokens=int(body.get("prompt_eval_count") or 0),
            completion_tokens=int(body.get("eval_count") or 0),
            latency_ms=(time.perf_counter() - started) * 1_000,
        )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return ToolTaskResult(
            task_id=task["task_id"],
            design=design,
            expected_tool=expected_tool,
            selected_tool=None,
            selected_arguments={},
            correct_tool=False,
            correct_arguments=False,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=(time.perf_counter() - started) * 1_000,
            error=str(exc),
        )


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def summarize(results: list[ToolTaskResult]) -> dict[str, dict[str, float]]:
    by_design: dict[str, list[ToolTaskResult]] = {}
    for result in results:
        by_design.setdefault(result.design, []).append(result)
    return {
        design: {
            "tasks": float(len(items)),
            "tool_selection_accuracy": sum(item.correct_tool for item in items) / len(items),
            "argument_accuracy": sum(item.correct_arguments for item in items) / len(items),
            "tokens_per_task": sum(item.tokens for item in items) / len(items),
            "p50_latency_ms": statistics.median(item.latency_ms for item in items),
            "p95_latency_ms": percentile([item.latency_ms for item in items], 0.95),
            "errors": float(sum(item.error is not None for item in items)),
        }
        for design, items in by_design.items()
    }


def run(*, base_url: str, model: str) -> dict[str, object]:
    tasks = load_tasks()
    results: list[ToolTaskResult] = []
    with httpx.Client(base_url=base_url, timeout=180) as client:
        tags = client.get("/api/tags")
        tags.raise_for_status()
        for design in DESIGNS:
            for task in tasks:
                results.append(run_task(client, model=model, design=design, task=task))
    failures = [result for result in results if result.error is not None]
    if failures:
        raise RuntimeError(
            f"Tool-design run had {len(failures)} runtime errors; no result should be reported."
        )
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "model": model,
            "temperature": 0,
            "seed": 4016,
            "task_count": len(tasks),
            "calls": len(results),
            "execution": "selection only; no tool was executed and no external state changed",
            "scoring": "exact JSON values and types; missing or additional arguments fail",
        },
        "designs": {
            "fine_grained": "14 single-purpose tools with production descriptions",
            "coarse_grained": "3 server-level action tools with an operation discriminator",
            "best_descriptions": "14 single-purpose tools with use/avoid boundary guidance",
        },
        "summary": summarize(results),
        "rows": [asdict(result) | {"tokens": result.tokens} for result in results],
    }


def rescore_existing(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        raise ValueError("Existing result does not contain prediction rows")
    tasks = {task["task_id"]: task for task in load_tasks()}
    results: list[ToolTaskResult] = []
    for row in raw["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Every result row must be an object")
        task_id = str(row["task_id"])
        design = str(row["design"])
        expected_tool, expected_args = expected_selection(tasks[task_id], design)
        selected_args = row.get("selected_arguments")
        if not isinstance(selected_args, dict):
            selected_args = {}
        selected_arguments = cast(dict[str, object], selected_args)
        selected_tool = row.get("selected_tool")
        results.append(
            ToolTaskResult(
                task_id=task_id,
                design=design,
                expected_tool=expected_tool,
                selected_tool=str(selected_tool) if selected_tool else None,
                selected_arguments=selected_arguments,
                correct_tool=selected_tool == expected_tool,
                correct_arguments=(
                    selected_tool == expected_tool
                    and arguments_match(selected_arguments, expected_args)
                ),
                prompt_tokens=int(row.get("prompt_tokens", 0)),
                completion_tokens=int(row.get("completion_tokens", 0)),
                latency_ms=float(row.get("latency_ms", 0)),
                error=str(row["error"]) if row.get("error") else None,
            )
        )
    failures = [result for result in results if result.error is not None]
    if failures:
        raise RuntimeError(f"Cannot report a run with {len(failures)} runtime errors")
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["scoring"] = "exact JSON values and types; missing or additional arguments fail"
    raw["metadata"] = metadata
    raw["summary"] = summarize(results)
    raw["rows"] = [asdict(result) | {"tokens": result.tokens} for result in results]
    return cast(dict[str, object], raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--output", default="evals/results/tool_design.json")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--rescore-existing", action="store_true")
    parser.add_argument("--model-digest")
    parser.add_argument("--runtime-version")
    args = parser.parse_args()
    tasks = load_tasks()
    for design in DESIGNS:
        tools_for(design)
        for task in tasks:
            expected_selection(task, design)
    if args.validate_only:
        print(f"Validated {len(tasks)} tasks across {len(DESIGNS)} designs")
        return
    destination = ROOT / args.output
    if args.rescore_existing:
        result = rescore_existing(destination)
        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            if args.model_digest:
                metadata["model_digest"] = args.model_digest
            if args.runtime_version:
                metadata["ollama_version"] = args.runtime_version
    else:
        result = run(base_url=args.base_url, model=args.model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
