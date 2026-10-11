# ACHDNLP Reference

Evidence-constrained reuse of historical expert diagnoses for congenital heart disease report research.

This repository is a readable, executable reference implementation of the manuscript's algorithmic structure. It is **not the archived clinical deployment**, and running it does not reproduce the paper's reported clinical results. The original clinical resource, complete ontology, prompts, fitted artifacts and execution manifests are not included. The bundled cases and rulebook are synthetic demonstration fixtures. No clinical data are distributed.

## Algorithm

```text
Historical findings + normalized expert labels
    -> sentence/evidence representation
    -> findings-only character TF-IDF index

Current findings
    -> explicit anatomy extraction
    -> anatomy-guided, diversity-constrained retrieval
    -> bounded historical excerpts + label priors
    -> structured candidate generation
    -> current-findings-only verification
    -> uncertainty-preserving decisions
    -> ordered suggestions and an auditable draft
```

Historical expert labels are added after case selection. The current expert impression and clinical reference labels are not inputs to inference. Generation and verification use separate payloads. Verification may demote suggestions but does not promote an initially uncertain candidate to definite output.

## Quick start

Python 3.11 or later is required. From the repository root:

```bash
python -m venv .venv
# Activate the environment using the command appropriate for your shell.
python -m pip install -e ".[dev]"
python -m achdnlp demo --all-arms
pytest
```

The demonstration runs locally without credentials or a network connection. Its deterministic backend is a test fixture, not an LLM and not a clinical baseline. Demonstration metrics are not evidence of diagnostic accuracy.

## Main programs

```bash
python build_db.py --input data/demo/history.jsonl --output runs/resource
python retrieve_generate.py --resource runs/resource --arms A,B,C,D --output runs/matched
python run_ablations.py --resource runs/resource --output runs/all
```

Inspect an individual ablation:

```bash
python experiments/03_findings_only.py --resource runs/resource
python experiments/04_preverification.py --resource runs/resource
python experiments/05_fixed_eight.py --resource runs/resource
```

All entry points call the same implementation; they do not contain divergent copies of the inference code.

## Experiment definitions

| Arm | Historical input | Generation / assessment |
|---|---|---|
| A | Selected findings and expert labels | Complete reference pipeline |
| B | None | A's nonhistory components unchanged |
| C | A's selected findings and order; explicit labels and label priors absent | A's nonhistory components unchanged |
| D | Exactly A's generation | Pre-verification snapshot; no second generation |
| R0 | Same as A | Alias of A; no extra inference |
| R8 / R14 | Fixed eight / fourteen selected exemplars | Otherwise A's pipeline |
| RULES_ONLY | None | Explicit current-findings rules; no model call |
| LLM_ONLY | None | No structured-anatomy input, rule supplementation or verification |
| TEXT_RAG | Lexically retrieved findings | No explicit labels, structured-anatomy input, rules or verification |
| LEXICAL_VERIFICATION | A's generation | Local lexical evidence check |
| SELF_REVIEW | A's generation | Same-service draft review |
| COUNT_MATCHED_GATING | A's generation | Random suppression matched to A's per-report definite count |
| ID_ONLY | A's generation | Disable diagnostic-name fallback |
| CF_LABELS | Same selected fragments, permuted historical labels | Offline counterfactual extension, not a reported clinical experiment |

A, B and C configurations are validated to differ only in historical input. A and C reuse a frozen retrieval result. D remains recoverable from A's generation even when A's verification fails. The count-matched control uses A's output count, never a clinical reference label.

The manuscript mentions eighteen original configurations but does not specify every original control at executable detail. This release implements the named designs above; it does not claim to recover the missing eighteen-configuration manifest. `ID_ONLY` is an additional mechanistic control. Fifteen configured entries include one alias and one future-direction extension; they are not fifteen independent clinical validations.

## Real model service

Use an authorized chat-completions-compatible endpoint. No service or model name is assumed to exist. Environment variables supply endpoint, model identifier and credentials:

```bash
export ACHDNLP_BASE_URL="https://your-authorized-service.example/v1"
export ACHDNLP_MODEL="your-model-identifier"
export ACHDNLP_API_KEY="your-local-credential"

python retrieve_generate.py --resource runs/resource \
  --backend configs/backend_http.yaml --allow-remote \
  --arms A,B,C,D --output runs/remote
```

In PowerShell, use `$env:ACHDNLP_MODEL = "..."` and equivalent assignments for the other variables. The service must return the documented JSON contract. `json_mode`, temperature transmission and token-parameter naming are explicit provider settings. Unsupported endpoints fail rather than silently replacing a response.

The eight files under `configs/backends/` retain the paper's archived alias names solely as labels. Each requires its own actual endpoint/model/key environment variables. They do not authenticate vendor model versions and are not automatically called by the demonstration.

Before using local research data, replace the demonstration ontology and rulebook, set `data_kind: local_research`, build a separate resource and use an explicitly authorized backend. The simple identifier lint is not a de-identification system. Output folders contain evidence quotations and must remain private.

## Data and evaluation

Historical JSONL rows require `record_id`, `findings` and `expert_labels`. Query rows contain only `record_id`, `findings`, optional `modality` and optional `cohort`; extra fields are rejected. Cohort is retained for grouping and is not sent to the model.

```bash
python -m achdnlp convert --input historical.csv --output historical.jsonl \
  --id-column case_id --findings-column "影像学表现" --labels-column expert_labels

python -m achdnlp evaluate \
  --predictions runs/matched/predictions.jsonl \
  --references data/demo/references.jsonl \
  --output runs/matched/metrics.json
```

The CSV label field contains canonical identifiers separated by `|`. Free-text expert impressions must be normalized locally before import; unknown labels are rejected. Query conversion deliberately omits clinical reference columns. No spreadsheet engine, OCR or imaging decoder is required.

Evaluation preserves suggestion order. An unresolved first suggestion is not dropped to promote a later hit. Missing references remain unscored; technical failures contribute no assistance. Whole-report quality is only evaluated when independent acceptability ratings are supplied. The package also exposes report-cluster ratios, crossed-reader bootstrap, ordinal paired analysis and agreement from pre-consensus ratings.

## Layout

```text
build_db.py                  Resource-building entry point
retrieve_generate.py        Inference entry point
run_ablations.py             Full declared experiment suite
src/achdnlp/resource.py      Findings-only index and portable artifacts
src/achdnlp/retrieval.py     Weighted retrieval and normalized-group diversity
src/achdnlp/capsule.py       Generator/verifier information boundaries
src/achdnlp/pipeline.py      Shared experiment execution
src/achdnlp/verification.py  Canonicalization, routing and evidence decisions
src/achdnlp/statistics.py    Paired, clustered and crossed statistical analysis
configs/                    Explicit experiment and service settings
data/demo/                  Synthetic fixtures and small example rulebook
experiments/                Individual ablation entry points
docs/                       Algorithms, provenance and release scope
tests/                      Behavioral, leakage, network-contract and statistical tests
validation/                 Local validation record; no clinical predictions
```

Start with `docs/algorithm.md`, then `configs/experiments.yaml` and `src/achdnlp/pipeline.py`. Details not specified by the manuscript are identified in `docs/parameter_provenance.md`; example defaults must not be described as recovered clinical settings.

## Release scope

See `docs/release_scope.md` for the exact disclosure boundary and a code-availability statement. `docs/reproducibility.md` describes artifacts, resumption and comparison invariants. `docs/publication_checklist.md` records publication-facing items that repository formatting alone cannot settle.

The software is distributed under the MIT license. It is research reference code, not a clinically validated medical product. Clinical use requires a separately governed and validated implementation. The license does not grant rights to third-party model services or to clinical datasets.
