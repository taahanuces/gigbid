# MCP Tool Inventory

Owned servers use the MCP Python SDK v2. Agent clients use the maintained `langchain.mcp` integration;
the assignment-named `langchain-mcp-adapters` package was archived and is incompatible with MCP v2.
See ADR 0004.

This table is populated from the servers' schema snapshots as tools are implemented.

| Tool | Server | Mode | Key annotations | Authentication |
| --- | --- | --- | --- | --- |
| `search_evidence` | Portfolio | Read | read-only, idempotent | bearer token |
| `get_case_study` | Portfolio | Read | read-only, idempotent | bearer token |
| `list_skills` | Portfolio | Read | read-only, idempotent | bearer token |
| `search_jobs` | Marketplace | Read | read-only, idempotent | bearer token |
| `get_job` | Marketplace | Read | read-only, idempotent | bearer token |
| `get_client_history` | Marketplace | Read | read-only, idempotent | bearer token |
| `get_connects_balance` | Marketplace | Read | read-only, idempotent | bearer token |
| `list_messages` | Marketplace | Read | read-only, idempotent | bearer token |
| `create_proposal_draft` | Marketplace | Write | non-destructive, idempotent | bearer token + approval |
| `submit_proposal` | Marketplace | Write | destructive, idempotent | bearer token + approval |
| `send_message` | Marketplace | Write | destructive, idempotent | bearer token + approval |
| `list_free_slots` | Workspace | Read | read-only, idempotent | bearer token |
| `create_tentative_hold` | Workspace | Write | non-destructive, idempotent | bearer token + approval |
| `create_email_draft` | Workspace | Write | non-destructive, idempotent | bearer token + approval |

Third-party trust rationales:

- Upwork: the platform's official OAuth-protected MCP endpoint is the only permitted live marketplace
  path and retains final confirmation on Upwork.
- GitHub: GitHub's official remote MCP server is restricted to read tools for code-backed portfolio
  ingestion, avoiding scraping and unreviewed repository writes.

