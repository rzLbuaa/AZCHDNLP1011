import copy
import json

import pytest
import yaml

from achdnlp.cli import main, read_jsonl_results
from achdnlp.evaluation import evaluate
from achdnlp.experiments import load_arms
from achdnlp.io import read_jsonl
from achdnlp.resource import Resource, build_resource
from achdnlp.runner import run_experiment
from achdnlp.schema import ClinicalReference, Verification


def test_ad_same_generation_and_zero_extra_calls(pipeline, queries):
    results = pipeline.process(queries[0], ["D", "A", "R0"])
    assert results["A"].generation == results["D"].generation
    assert results["A"].audit["generation_hash"] == results["D"].audit["generation_hash"]
    assert results["D"].audit["calls_this_arm"] == 0
    assert results["R0"].audit["calls_this_arm"] == 0
    assert sum(c["stage"] == "generate" for c in pipeline.backend.calls) == 1


def test_c_fixed_retrieval_and_b_no_history(pipeline, queries):
    results = pipeline.process(queries[0], ["A", "B", "C"])
    assert results["A"].audit["history_selection_hash"] == results["C"].audit["history_selection_hash"]
    assert results["B"].retrieval == []


def test_count_matched_controls(pipeline, queries):
    results = pipeline.process(queries[0], ["A", "D", "COUNT_MATCHED_GATING"])
    assert results["A"].audit["final_definite"] == results["COUNT_MATCHED_GATING"].audit["final_definite"]
    assert results["D"].generation == results["COUNT_MATCHED_GATING"].generation


def test_all_arms_execute(pipeline, queries):
    for query in queries:
        results = pipeline.process(query, list(pipeline.arms))
        assert all(result.status == "completed" for result in results.values())
        assert len(results) == 15


def test_d_survives_parent_verification_failure(pipeline, queries):
    original = pipeline.backend.call
    def call(stage, payload):
        if stage == "verify":
            return Verification(verdicts=[])
        return original(stage, payload)
    pipeline.backend.call = call
    results = pipeline.process(queries[0], ["A", "D"])
    assert results["A"].status == "technical_failure"
    assert results["D"].status == "completed"
    assert results["D"].audit["calls_this_arm"] == 0


def test_counterfactual_only_changes_history_labels(pipeline, queries):
    results = pipeline.process(queries[0], ["A", "CF_LABELS"])
    normal, changed = results["A"], results["CF_LABELS"]
    assert normal.audit["query_hash"] == changed.audit["query_hash"]
    assert normal.audit["history_selection_hash"] == changed.audit["history_selection_hash"]
    assert [x.expert_labels for x in normal.retrieval] != [x.expert_labels for x in changed.retrieval]


def test_invalid_matched_configs_fail(project, tmp_path):
    config = yaml.safe_load((project / "configs/experiments.yaml").read_text())
    config["arms"][1]["supplement_rules"] = False
    target = tmp_path / "bad.yaml"
    target.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="differ only"):
        load_arms(target)


def test_resource_integrity_failure(project, tmp_path, ontology, rules):
    output = tmp_path / "resource"
    build_resource(project / "data/demo/history.jsonl", output, ontology, rules)
    with (output / "records.jsonl").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="integrity"):
        Resource.load(output, ontology, rules)


def test_resource_refuses_overwrite(project, tmp_path, ontology, rules):
    output = tmp_path / "resource"
    build_resource(project / "data/demo/history.jsonl", output, ontology, rules)
    with pytest.raises(FileExistsError):
        build_resource(project / "data/demo/history.jsonl", output, ontology, rules)


def test_resume_manifest_and_evaluation(project, tmp_path, ontology, rules):
    resource = tmp_path / "resource"
    build_resource(project / "data/demo/history.jsonl", resource, ontology, rules)
    arguments = dict(queries_path=project / "data/demo/queries.jsonl", resource_path=resource,
                     study_path=project / "configs/study.yaml", arms_path=project / "configs/experiments.yaml",
                     backend_path=project / "configs/backend_demo.yaml", output=tmp_path / "run",
                     names=["A", "B", "C", "D"])
    first = run_experiment(**arguments)
    outputs = (tmp_path / "run/predictions.jsonl").read_bytes()
    assert run_experiment(**arguments) == first
    assert (tmp_path / "run/predictions.jsonl").read_bytes() == outputs
    results = read_jsonl_results(tmp_path / "run/predictions.jsonl")
    refs = read_jsonl(project / "data/demo/references.jsonl", ClinicalReference)
    metrics = evaluate(results, refs, resamples=1000)
    assert metrics["data_kinds"] == ["demonstration"]
    assert metrics["arms"]["A"]["completion"]["hits"] == 8
    assert metrics["arms"]["A"]["whole_report_acceptability"]["all_input_rate"] is None
    with pytest.raises(ValueError, match="identity differs"):
        run_experiment(**{**arguments, "names": ["A"]})


def test_cli_build_and_run(project, tmp_path, monkeypatch):
    monkeypatch.chdir(project)
    assert main(["build", "--output", str(tmp_path / "resource")]) == 0
    assert main(["run", "--resource", str(tmp_path / "resource"),
                 "--output", str(tmp_path / "run"), "--arms", "A,B,C,D"]) == 0


def test_references_never_in_inference_payloads(pipeline, queries):
    payloads = []
    original = pipeline.backend.call
    def capture(stage, payload):
        payloads.append((stage, copy.deepcopy(payload)))
        return original(stage, payload)
    pipeline.backend.call = capture
    pipeline.process(queries[0], ["A", "B", "C"])
    assert all("clinical_reference" not in json.dumps(payload) for _, payload in payloads)
    gen = [payload for stage, payload in payloads if stage == "generate"]
    assert len(gen) == 3
    assert gen[1]["historical_exemplars"] == [] and gen[1]["label_priors"] == []
    assert gen[2]["historical_exemplars"] and gen[2]["label_priors"] == []
    assert all("expert_labels" not in x for x in gen[2]["historical_exemplars"])


def test_resource_builder_fingerprint(project, tmp_path, ontology, rules):
    output = tmp_path / "resource"
    build_resource(project / "data/demo/history.jsonl", output, ontology, rules)
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["builder_hash"] = "different-construction-version"
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="construction code differs"):
        Resource.load(output, ontology, rules)
