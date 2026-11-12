# ADR 0004: Use LangChain's maintained MCP client

## Status

Accepted on 10 November 2026.

## Context

The assignment names `langchain-mcp-adapters`, but that package was archived in September 2026 and
its final release cannot import with the stable MCP Python SDK v2: it imports the removed
`mcp.shared.context.RequestContext`. LangChain moved maintained MCP support into `langchain.mcp`.

## Decision

Use the official MCP Python SDK v2 for owned servers and `langchain[mcp]` / `langchain.mcp` for agent
client integration. Do not patch an archived package or downgrade the protocol SDK. Keep the adapter
behind `agent/mcp_client.py` so this ecosystem migration does not affect graph nodes.

## Consequences

The implementation follows the current maintained libraries while preserving the assignment's intended
MCP-to-LangGraph boundary. This dependency decision must be explained in the viva and pinned in the
final lock/environment evidence.
