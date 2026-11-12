from agent.handoffs import DataOrigin
from data.pipelines.generate_synthetic_personas import (
    GENERATOR_VERSION,
    PERSONAS,
    benchmark_jobs,
    evidence_for,
)


def test_each_synthetic_persona_has_required_corpus_and_provenance() -> None:
    for persona in PERSONAS:
        evidence = evidence_for(persona)
        assert len(persona.projects) == 15
        assert sum(item.type == "case_study" for item in evidence) == 15
        assert sum(item.type == "past_proposal" for item in evidence) == 150
        assert len(evidence) == 210
        assert all(item.data_origin == DataOrigin.SYNTHETIC for item in evidence)
        assert all(item.generator_version == GENERATOR_VERSION for item in evidence)


def test_benchmark_gold_set_covers_relevant_same_project_evidence() -> None:
    for persona in PERSONAS:
        jobs = benchmark_jobs(persona)
        assert len(jobs) == 30
        for job in jobs:
            gold = job["gold_evidence_ids"]
            assert isinstance(gold, list)
            assert len(gold) == 10
            project_prefix = str(gold[0]).rsplit(":", maxsplit=1)[0]
            assert all(str(evidence_id).startswith(project_prefix) for evidence_id in gold)
            assert job["provenance"] == {
                "data_origin": "synthetic",
                "generator_version": GENERATOR_VERSION,
            }
