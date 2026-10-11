import argparse
import json
import sys
from pathlib import Path

from .config import load_study
from .evaluation import evaluate
from .experiments import load_arms
from .io import atomic_json, csv_to_records, read_jsonl, write_jsonl
from .ontology import Ontology
from .resource import build_resource
from .rules import RuleEngine
from .runner import run_experiment
from .schema import CaseResult, ClinicalReference, HistoricalRecord, Query


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="achdnlp")
    commands = root.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build a findings-only lexical index and case resource")
    build.add_argument("--input", type=Path, default=Path("data/demo/history.jsonl"))
    build.add_argument("--output", type=Path, default=Path("runs/resource"))
    build.add_argument("--study", type=Path, default=Path("configs/study.yaml"))
    run = commands.add_parser("run", help="Execute matched inference or declared controls")
    run.add_argument("--queries", type=Path, default=Path("data/demo/queries.jsonl"))
    run.add_argument("--resource", type=Path, default=Path("runs/resource"))
    run.add_argument("--study", type=Path, default=Path("configs/study.yaml"))
    run.add_argument("--experiments", type=Path, default=Path("configs/experiments.yaml"))
    run.add_argument("--backend", type=Path, default=Path("configs/backend_demo.yaml"))
    run.add_argument("--output", type=Path, default=Path("runs/matched"))
    run.add_argument("--arms", default="A,B,C,D")
    run.add_argument("--allow-remote", action="store_true")
    evaluate_cmd = commands.add_parser("evaluate", help="Score stored predictions against separate references")
    evaluate_cmd.add_argument("--predictions", type=Path, required=True)
    evaluate_cmd.add_argument("--references", type=Path, required=True)
    evaluate_cmd.add_argument("--output", type=Path, required=True)
    evaluate_cmd.add_argument("--resamples", type=int, default=20000)
    evaluate_cmd.add_argument("--seed", type=int, default=2026)
    convert = commands.add_parser("convert", help="Project explicitly mapped CSV columns into JSONL")
    convert.add_argument("--input", type=Path, required=True)
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument("--id-column", required=True)
    convert.add_argument("--findings-column", required=True)
    convert.add_argument("--labels-column")
    convert.add_argument("--modality-column")
    convert.add_argument("--cohort-column")
    commands.add_parser("arms", help="List the declared experiment switches")
    demo = commands.add_parser("demo", help="Execute the offline demonstration without credentials")
    demo.add_argument("--output", type=Path, default=Path("runs/demo"))
    demo.add_argument("--all-arms", action="store_true")
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "build":
            study = load_study(args.study)
            result = build_resource(args.input, args.output, Ontology.load(Path(study.ontology)),
                                    RuleEngine(Path(study.rulebook)), study.data_kind)
        elif args.command == "run":
            names = (list(load_arms(args.experiments)) if args.arms == "all" else args.arms.split(","))
            result = run_experiment(queries_path=args.queries, resource_path=args.resource,
                                    study_path=args.study, arms_path=args.experiments,
                                    backend_path=args.backend, output=args.output,
                                    names=names, allow_remote=args.allow_remote)
        elif args.command == "evaluate":
            result = evaluate(read_jsonl_results(args.predictions),
                              read_jsonl(args.references, ClinicalReference),
                              resamples=args.resamples, seed=args.seed)
            atomic_json(args.output, result)
        elif args.command == "convert":
            rows = csv_to_records(args.input, id_column=args.id_column,
                                  findings_column=args.findings_column, labels_column=args.labels_column,
                                  modality_column=args.modality_column, cohort_column=args.cohort_column)
            schema = HistoricalRecord if args.labels_column else Query
            valid = [schema.model_validate(row) for row in rows]
            ids = [row.record_id for row in valid]
            if len(ids) != len(set(ids)):
                raise ValueError("record IDs must be unique")
            write_jsonl(args.output, valid)
            result = {"records": len(valid), "schema": schema.__name__}
        elif args.command == "arms":
            result = {name: arm.model_dump() for name, arm in load_arms(Path("configs/experiments.yaml")).items()}
        else:
            study_path = Path("configs/study.yaml")
            study = load_study(study_path)
            resource = args.output / "resource"
            if not resource.exists():
                build_resource(Path("data/demo/history.jsonl"), resource,
                               Ontology.load(Path(study.ontology)), RuleEngine(Path(study.rulebook)))
            names = list(load_arms(Path("configs/experiments.yaml"))) if args.all_arms else ["A", "B", "C", "D", "R8", "R14"]
            output = args.output / "evaluation"
            result = run_experiment(queries_path=Path("data/demo/queries.jsonl"), resource_path=resource,
                                    study_path=study_path, arms_path=Path("configs/experiments.yaml"),
                                    backend_path=Path("configs/backend_demo.yaml"), output=output, names=names)
            metrics = evaluate(read_jsonl_results(output / "predictions.jsonl"),
                               read_jsonl(Path("data/demo/references.jsonl"), ClinicalReference), resamples=2000)
            metrics["data_origin"] = "synthetic demonstration; not clinical performance"
            atomic_json(output / "metrics.json", metrics)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


def read_jsonl_results(path: Path) -> list[CaseResult]:
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(CaseResult.model_validate_json(line))
            except ValueError:
                raise ValueError(f"invalid prediction record at row {index}") from None
    if not rows:
        raise ValueError("empty predictions file")
    return rows
