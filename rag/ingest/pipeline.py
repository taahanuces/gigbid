from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Iterable
from pathlib import Path

from pypdf import PdfReader

from agent.handoffs import EvidenceItem

HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def _stable_id(source: Path, index: int, content: str) -> str:
    digest = hashlib.sha256(f"{source}:{index}:{content}".encode()).hexdigest()[:16]
    return f"evidence-{digest}"


def _chunks(text: str, *, size: int = 700, overlap: int = 100) -> Iterable[str]:
    words = text.split()
    start = 0
    while start < len(words):
        end = min(len(words), start + size)
        yield " ".join(words[start:end])
        if end == len(words):
            break
        start = max(start + 1, end - overlap)


class IngestionPipeline:
    def __init__(self, *, tenant_id: str, persona: str) -> None:
        self.tenant_id = tenant_id
        self.persona = persona

    def load_pdf(self, path: str | Path, **metadata: object) -> list[EvidenceItem]:
        source = Path(path)
        reader = PdfReader(source)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return self._items(source, text, "cv", metadata)

    def load_pdf_bytes(
        self, content: bytes, *, filename: str, **metadata: object
    ) -> list[EvidenceItem]:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return self._items(Path(filename), text, "cv", metadata)

    def load_text(
        self,
        text: str,
        *,
        filename: str,
        item_type: str = "case_study",
        **metadata: object,
    ) -> list[EvidenceItem]:
        source = Path(filename)
        title_match = HEADING_PATTERN.search(text)
        title = title_match.group(1) if title_match else source.stem.replace("_", " ")
        return self._items(source, text, item_type, {"title": title, **metadata})

    def load_markdown(self, path: str | Path, **metadata: object) -> list[EvidenceItem]:
        source = Path(path)
        text = source.read_text(encoding="utf-8")
        title_match = HEADING_PATTERN.search(text)
        title = title_match.group(1) if title_match else source.stem.replace("_", " ")
        return self._items(source, text, "case_study", {"title": title, **metadata})

    def load_code(self, path: str | Path, **metadata: object) -> list[EvidenceItem]:
        source = Path(path)
        text = source.read_text(encoding="utf-8", errors="replace")
        return self._items(source, text, "code", metadata)

    def load_json_records(
        self, path: str | Path, *, record_type: str, **metadata: object
    ) -> list[EvidenceItem]:
        source = Path(path)
        records = json.loads(source.read_text(encoding="utf-8"))
        items: list[EvidenceItem] = []
        for index, record in enumerate(records):
            content = str(record.get("text") or record.get("body") or record.get("summary") or "")
            items.extend(
                self._items(
                    source,
                    content,
                    record_type,
                    {**metadata, **record, "source_index": index},
                )
            )
        return items

    def _items(
        self,
        source: Path,
        text: str,
        item_type: str,
        metadata: dict[str, object],
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for index, content in enumerate(_chunks(text)):
            items.append(
                EvidenceItem(
                    evidence_id=_stable_id(source, index, content),
                    tenant_id=self.tenant_id,
                    persona=self.persona,
                    type=item_type,
                    title=str(metadata.get("title") or source.stem.replace("_", " ")),
                    text=content,
                    source=str(source),
                    date=_optional_text(metadata.get("date")),
                    project=_optional_text(metadata.get("project")),
                    skills=_string_list(metadata.get("skills")),
                    client_industry=_optional_text(metadata.get("client_industry")),
                    outcome=_optional_text(metadata.get("outcome")),
                    data_origin=str(
                        metadata.get("data_origin") or "private_user_data_not_committed"
                    ),
                    generator_version=_optional_text(metadata.get("generator_version")),
                )
            )
        return items


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value]


class IncrementalManifest:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, str] = (
            json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        )

    @staticmethod
    def fingerprint(path: str | Path) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def changed(self, path: str | Path) -> bool:
        key = str(Path(path).resolve())
        return self.entries.get(key) != self.fingerprint(path)

    def mark_indexed(self, path: str | Path) -> None:
        key = str(Path(path).resolve())
        self.entries[key] = self.fingerprint(path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2, sort_keys=True), encoding="utf-8")
