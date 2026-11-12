# AI Usage Disclosure

| Date | Tool | Work assisted | Human verification / correction |
| --- | --- | --- | --- |
| 2026-11-10 | OpenAI Codex | Requirement analysis, project contracts, initial implementation | All generated code is reviewed against the assignment and tested before acceptance. Corrections will be recorded here as they occur. |
| 2026-11-10 | OpenAI Codex | MCP, RAG, LangGraph, API, dashboard, tests and packaging | Caught and replaced the archived `langchain-mcp-adapters` client after its MCP v2 import failed; also corrected a tool-prefix allowlist bug and an MCP container command that required an uninstalled CLI extra. |
| 2026-11-11 | OpenAI Codex | Simulator, product APIs, worker execution, open-model routing, UI and evaluations | Live public-data smoke testing exposed nullable budgets that the first schema rejected; browser/API review also caught a hard-coded frontend price floor that bypassed persisted user settings. Both were corrected and regression-tested. |

The instructor starter kit was inspected as a reference scaffold only. The implementation and synthetic
smoke records in this repository were created independently.

