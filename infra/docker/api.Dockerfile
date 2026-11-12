FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY agent agent
COPY apps apps
COPY evals evals
COPY data data
COPY mcp_servers mcp_servers
COPY rag rag
COPY scripts scripts
COPY worker worker
RUN pip install --no-cache-dir . && python -m data.pipelines.generate_synthetic_personas
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

