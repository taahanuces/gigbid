from evals.runners.tool_design_eval import (
    DESIGNS,
    ToolTaskResult,
    arguments_match,
    load_tasks,
    summarize,
    tools_for,
)


def test_tool_design_dataset_has_exactly_40_known_call_tasks() -> None:
    tasks = load_tasks()
    assert len(tasks) == 40
    assert len({task["task_id"] for task in tasks}) == 40
    assert all(task["expected_tool"] for task in tasks)


def test_all_three_tool_designs_have_valid_schemas() -> None:
    counts = {design: len(tools_for(design)) for design in DESIGNS}
    assert counts == {
        "fine_grained": 14,
        "coarse_grained": 3,
        "best_descriptions": 14,
    }


def test_argument_scoring_rejects_wrong_types_and_extra_keys() -> None:
    assert arguments_match({"k": 5}, {"k": 5})
    assert not arguments_match({"k": "5"}, {"k": 5})
    assert not arguments_match({"k": 5, "extra": True}, {"k": 5})


def test_summary_reports_selection_arguments_tokens_and_latency() -> None:
    result = ToolTaskResult(
        task_id="TD01",
        design="fine_grained",
        expected_tool="search_jobs",
        selected_tool="search_jobs",
        selected_arguments={},
        correct_tool=True,
        correct_arguments=False,
        prompt_tokens=10,
        completion_tokens=2,
        latency_ms=100,
    )
    summary = summarize([result])["fine_grained"]
    assert summary["tool_selection_accuracy"] == 1
    assert summary["argument_accuracy"] == 0
    assert summary["tokens_per_task"] == 12
