from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent.security import redact_pii


class AppendOnlyAuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        user_id: str,
        tool: str,
        arguments: dict[str, object],
        result: dict[str, object],
        trace_id: str,
    ) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "tool": tool,
            "arguments": arguments,
            "result": result,
            "trace_id": trace_id,
        }
        serialized = redact_pii(json.dumps(event, sort_keys=True, default=str))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(serialized + "\n")
