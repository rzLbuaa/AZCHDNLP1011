import json
import os
import platform
from contextlib import contextmanager
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

from . import __version__
from .backend import DemoBackend, HTTPBackend
from .config import BackendConfig, load_study, load_yaml
from .experiments import load_arms
from .io import atomic_json, digest, file_hash, read_jsonl, write_jsonl
from .ontology import Ontology
from .pipeline import Pipeline
from .resource import Resource
from .rules import RuleEngine
from .schema import CaseResult, Query
from .text import normalized


def code_fingerprint() -> str:
    root = Path(__file__).parent
    paths = sorted([*root.glob("*.py"), *root.glob("prompts/*.txt")])
    return digest({str(p.relative_to(root)): file_hash(p) for p in paths})


@contextmanager
def run_lock(output: Path):
    lock = output / ".run.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("run directory is locked; verify no process is active before removing the lock") from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def run_experiment(*, queries_path: Path, resource_path: Path, study_path: Path,
                   arms_path: Path, backend_path: Path, output: Path, names: list[str],
                   allow_remote: bool = False) -> dict:
    study = load_study(study_path)
    ontology, rules = Ontology.load(Path(study.ontology)), RuleEngine(Path(study.rulebook))
    resource = Resource.load(resource_path, ontology, rules)
    queries = read_jsonl(queries_path, Query)
    arms = load_arms(arms_path)
    if len(names) != len(set(names)) or not set(names) <= arms.keys():
        raise ValueError("arm selection contains duplicates or unknown names")
    groups = {r.group_id for r in resource.records}
    if any(digest(normalized(q.findings)) in groups for q in queries):
        raise ValueError("exact normalized-text overlap between historical and evaluation inputs")
    if resource.manifest["data_kind"] != study.data_kind:
        raise ValueError("resource and experiment data_kind must agree")
    backend_config = BackendConfig.model_validate(load_yaml(backend_path))
    if backend_config.kind == "demo" and study.data_kind != "demonstration":
        raise ValueError("demo backend is restricted to demonstration data")
    backend = (DemoBackend(ontology, rules) if backend_config.kind == "demo" else
               HTTPBackend(backend_config, allow_remote=allow_remote))
    identity = {
        "release": __version__, "code_hash": code_fingerprint(), "input_hash": file_hash(queries_path),
        "resource_hash": resource.fingerprint, "ontology_hash": ontology.fingerprint,
        "rulebook_hash": rules.fingerprint, "backend": backend.identity(),
        "study": study.model_dump(exclude={"ontology", "rulebook"}),
        "arms": {key: value.model_dump() for key, value in arms.items()}, "selected_arms": names,
        "python": platform.python_version(),
        "dependencies": {name: version(name) for name in ["numpy", "scipy", "scikit-learn", "pydantic", "httpx", "PyYAML"]},
    }
    manifest = {"fingerprint": digest(identity), **identity}
    output.mkdir(parents=True, exist_ok=True)
    try:
        with run_lock(output):
            existing = output / "manifest.json"
            if existing.exists():
                old = json.loads(existing.read_text(encoding="utf-8"))
                if old.get("fingerprint") != manifest["fingerprint"] or digest({k: v for k, v in old.items() if k != "fingerprint"}) != old["fingerprint"]:
                    raise ValueError("run identity differs; use a new output directory")
            elif list(output.glob("records/*.json")):
                raise ValueError("checkpoint files exist without a manifest")
            else:
                atomic_json(existing, manifest)
                target = output / "prompts"
                target.mkdir(exist_ok=True)
                for name in ("generate", "verify", "self_review"):
                    source = files("achdnlp").joinpath("prompts", name + ".txt")
                    (target / (name + ".txt")).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            pipeline = Pipeline(resource, ontology, rules, backend, study, arms)
            results = []
            for query in queries:
                checkpoint = output / "records" / (query.record_id + ".json")
                if checkpoint.exists():
                    record = json.loads(checkpoint.read_text(encoding="utf-8"))
                    if record["query_hash"] != digest(query.model_dump()):
                        raise ValueError("checkpoint query mismatch")
                    if digest(record["results"]) != record["result_hash"]:
                        raise ValueError("checkpoint content hash mismatch")
                    current = [CaseResult.model_validate(x) for x in record["results"]]
                    if {x.arm for x in current} != set(names):
                        raise ValueError("checkpoint arm coverage mismatch")
                else:
                    before_calls = len(backend.calls)
                    current = list(pipeline.process(query, names).values())
                    payload = [r.model_dump() for r in current]
                    atomic_json(checkpoint, {"query_hash": digest(query.model_dump()), "results": payload,
                                             "result_hash": digest(payload),
                                             "calls": backend.calls[before_calls:]})
                results.extend(current)
            write_jsonl(output / "predictions.jsonl", results)
            summary = {name: {"inputs": len(queries),
                              "completed": sum(r.status == "completed" for r in results if r.arm == name)}
                       for name in names}
            atomic_json(output / "completion.json", {"data_kind": study.data_kind, "arms": summary})
            return summary
    finally:
        backend.close()
