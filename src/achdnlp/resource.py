import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from .io import atomic_json, digest, file_hash, read_jsonl, write_jsonl
from .ontology import Ontology
from .privacy import check_text
from .rules import RuleEngine
from .schema import HistoricalRecord, ResourceRecord
from .text import normalized, sentences

RESOURCE_FILES = ("records.jsonl", "vocabulary.json", "idf.npy", "matrix.npz")


def builder_fingerprint() -> str:
    root = Path(__file__).parent
    return digest({name: file_hash(root / name) for name in
                   ("resource.py", "text.py", "schema.py", "ontology.py", "rules.py")})


class Resource:
    def __init__(self, records, vectorizer, matrix, manifest):
        self.records = records
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.manifest = manifest
        self.fingerprint = digest(manifest)

    @classmethod
    def load(cls, directory: Path, ontology: Ontology, rules: RuleEngine):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest["format_version"] != 1:
            raise ValueError("unsupported resource version")
        if manifest.get("builder_hash") != builder_fingerprint():
            raise ValueError("resource construction code differs; rebuild the index")
        if manifest["ontology_hash"] != ontology.fingerprint or manifest["rulebook_hash"] != rules.fingerprint:
            raise ValueError("resource ontology/rulebook mismatch; rebuild the index")
        if manifest["sklearn_version"] != version("scikit-learn"):
            raise ValueError("resource scikit-learn version differs; rebuild under the current environment")
        for name in RESOURCE_FILES:
            if file_hash(directory / name) != manifest["files"][name]:
                raise ValueError(f"resource integrity failure: {name}")
        records = read_jsonl(directory / "records.jsonl", ResourceRecord)
        vocabulary = json.loads((directory / "vocabulary.json").read_text(encoding="utf-8"))
        vectorizer = make_vectorizer(vocabulary)
        vectorizer.idf_ = np.load(directory / "idf.npy", allow_pickle=False)
        matrix = sparse.load_npz(directory / "matrix.npz").tocsr()
        if matrix.shape != (len(records), len(vocabulary)):
            raise ValueError("resource dimensions do not match")
        return cls(records, vectorizer, matrix, manifest)


def make_vectorizer(vocabulary=None):
    return TfidfVectorizer(analyzer="char", ngram_range=(2, 5), lowercase=False,
                           norm="l2", sublinear_tf=True, vocabulary=vocabulary)


def build_resource(source: Path, output: Path, ontology: Ontology, rules: RuleEngine,
                   data_kind: str = "demonstration") -> dict:
    if output.exists():
        raise FileExistsError("resource output already exists; choose a new directory")
    rows = read_jsonl(source, HistoricalRecord)
    records = []
    for row in rows:
        check_text(row.findings)
        current = sentences(row.findings)
        records.append(ResourceRecord(
            record_id=row.record_id, group_id=digest(normalized(row.findings)),
            findings=row.findings, sentences=current, anatomy=rules.anatomy(current),
            modality=row.modality, expert_labels=list(dict.fromkeys(
                ontology.normalize_label(label) for label in row.expert_labels
            )), source=row.source,
        ))
    vectorizer = make_vectorizer()
    matrix = vectorizer.fit_transform([normalized(row.findings) for row in records])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".resource-", dir=output.parent))
    try:
        write_jsonl(temporary / "records.jsonl", records)
        atomic_json(temporary / "vocabulary.json", {
            str(key): int(value) for key, value in vectorizer.vocabulary_.items()
        })
        np.save(temporary / "idf.npy", vectorizer.idf_, allow_pickle=False)
        sparse.save_npz(temporary / "matrix.npz", matrix.tocsr())
        manifest = {
            "format_version": 1, "builder_hash": builder_fingerprint(),
            "data_kind": data_kind, "records": len(records),
            "normalized_groups": len({r.group_id for r in records}),
            "source_hash": file_hash(source), "ontology_hash": ontology.fingerprint,
            "rulebook_hash": rules.fingerprint, "sklearn_version": version("scikit-learn"),
            "vectorizer": {"analyzer": "char", "ngram_range": [2, 5], "sublinear_tf": True},
            "index_inputs": ["findings"],
            "files": {name: file_hash(temporary / name) for name in RESOURCE_FILES},
        }
        atomic_json(temporary / "manifest.json", manifest)
        temporary.rename(output)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
