.PHONY: dev api web worker simulator test test-unit test-integration test-postgres lint format eval eval-smoke eval-synthetic-rag eval-rag-ablation eval-simulator-outcomes eval-tools eval-model-profiles eval-human-prep eval-judge-calibration eval-portfolio-builder agent-design-data eval-agent-design eval-agent-model-design synthetic-data simulator-data seed demo openapi data-fetch data-prepare public-profile data

dev:
	docker compose -f infra/docker-compose.yml up --build

api:
	uvicorn apps.api.main:app --reload --port 8000

web:
	cd apps/web && pnpm dev

worker:
	celery -A worker.celery_app worker --loglevel=INFO

simulator:
	uvicorn apps.simulator.main:app --reload --port 8081

test:
	pytest --cov=agent --cov=rag --cov=mcp_servers

test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration

test-postgres:
	TEST_POSTGRES_URL=postgresql+psycopg://gigbid:gigbid@localhost:5432/gigbid pytest tests/integration/test_postgres_durability.py

lint:
	ruff check .
	mypy agent apps mcp_servers rag worker data/pipelines evals
	cd apps/web && pnpm lint

format:
	ruff format .

eval: eval-smoke eval-synthetic-rag eval-rag-ablation eval-simulator-outcomes

eval-smoke:
	python -m evals.runners.run_all --smoke

synthetic-data:
	python -m data.pipelines.generate_synthetic_personas

eval-synthetic-rag: synthetic-data
	python -m evals.runners.synthetic_rag_eval

eval-rag-ablation: synthetic-data
	python -m evals.runners.rag_ablation

eval-simulator-outcomes: synthetic-data
	python -m evals.runners.simulator_outcomes

eval-tools:
	python -m evals.runners.tool_design_eval --base-url $${OLLAMA_BASE_URL:-http://127.0.0.1:11434} --model $${TOOL_MODEL:-llama3.1:8b}

eval-model-profiles: synthetic-data
	python -m evals.runners.model_profile_eval --base-url $${OLLAMA_BASE_URL:-http://127.0.0.1:11434} --models $${MODEL_CANDIDATES:-qwen3:4b llama3.1:8b}

eval-human-prep: synthetic-data
	python -m evals.runners.prepare_human_studies

eval-judge-calibration:
	python -m evals.runners.judge_calibration

eval-portfolio-builder:
	python -m evals.runners.portfolio_builder_eval

agent-design-data:
	python -m data.pipelines.build_agent_design_dataset

simulator-data:
	python -m data.pipelines.build_simulator_fixture

eval-agent-design: synthetic-data agent-design-data
	python -m evals.runners.agent_design_eval

eval-agent-model-design: synthetic-data
	python -m evals.runners.agent_model_design_eval --base-url $${OLLAMA_BASE_URL:-http://127.0.0.1:11434} --models $${MODEL_CANDIDATES:-qwen3:4b llama3.1:8b}

seed:
	python -m apps.api.seed

demo:
	python -m evals.runners.demo_vertical_slice

openapi:
	python -m apps.api.export_openapi

data-fetch:
	python -m data.pipelines.fetch_kaggle

data-prepare:
	python -m data.pipelines.prepare_kaggle

public-profile:
	python -m data.pipelines.build_public_profiles

data: data-fetch data-prepare public-profile

