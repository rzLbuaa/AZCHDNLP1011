import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def canonical_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(canonical_json(data) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_jsonl(path: Path, schema: type[T]) -> list[T]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(schema.model_validate_json(line))
        except ValueError:
            raise ValueError(f"invalid {schema.__name__} at row {i}; check the declared schema") from None
    ids = [row.record_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("record_id values must be unique")
    if not rows:
        raise ValueError("input contains no records")
    return rows


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(canonical_json(row.model_dump() if isinstance(row, BaseModel) else row) + "\n"
                   for row in rows)
    path.write_text(text, encoding="utf-8")


def csv_to_records(path: Path, *, id_column: str, findings_column: str,
                   labels_column: str | None = None, modality_column: str | None = None,
                   cohort_column: str | None = None) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = [id_column, findings_column, labels_column, modality_column, cohort_column]
        if any(key and key not in (reader.fieldnames or []) for key in required):
            raise ValueError("a mapped CSV column is absent")
        output = []
        for row in reader:
            item = {"record_id": row[id_column], "findings": row[findings_column]}
            if labels_column:
                item["expert_labels"] = [s.strip() for s in row[labels_column].split("|") if s.strip()]
            if modality_column:
                item["modality"] = row[modality_column] or None
            if cohort_column:
                item["cohort"] = row[cohort_column] or "unspecified"
            output.append(item)
        return output
