FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY agent agent
COPY mcp_servers mcp_servers
COPY rag rag
COPY data/processed/personas data/processed/personas
RUN pip install --no-cache-dir .

