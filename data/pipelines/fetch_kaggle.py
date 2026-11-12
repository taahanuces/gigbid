from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data/sources.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_sources() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return dict(payload["sources"])


def fetch_source(name: str, source: dict[str, Any], destination: Path) -> Path:
    target = destination / str(source["archive_name"])
    expected = str(source["sha256"])
    if target.exists() and sha256_file(target) == expected:
        return target

    url = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        f"{source['kaggle_ref']}?datasetVersionNumber={source['version']}"
    )
    temporary = target.with_suffix(".download")
    request = urllib.request.Request(  # noqa: S310 - URL is built from reviewed registry entries
        url, headers={"User-Agent": "GigBid-Dataset-Builder/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"Checksum mismatch for {name}: expected {expected}, received {actual}")
    temporary.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Download immutable Kaggle dataset versions")
    parser.add_argument("--all", action="store_true", help="also fetch excluded sources")
    parser.add_argument("--source", action="append", default=[], help="fetch one registry key")
    parser.add_argument("--destination", default="data/raw/kaggle")
    args = parser.parse_args()

    sources = load_sources()
    requested = set(args.source)
    unknown = requested.difference(sources)
    if unknown:
        raise SystemExit(f"Unknown source keys: {', '.join(sorted(unknown))}")
    selected = {
        name: source
        for name, source in sources.items()
        if args.all or name in requested or (not requested and source.get("selected"))
    }
    destination = ROOT / args.destination
    destination.mkdir(parents=True, exist_ok=True)
    for name, source in selected.items():
        path = fetch_source(name, source, destination)
        print(f"verified {name}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
