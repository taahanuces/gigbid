from __future__ import annotations

import json
from pathlib import Path

from apps.api.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "web/openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
