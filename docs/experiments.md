# Experiment contracts

`configs/experiments.yaml` is the executable registry. `experiments/*.py` contains thin, individually runnable entry points. All paths and provider behavior are shared; there are no arm-specific clinical answers.

| Entry | Changed component | Shared information | Status in this release |
|---|---|---|---|
| A / B | Historical context on/off | Current input, prompt, backend, index, parser, rules, maximum budget | Matched manuscript design |
| A / C | Explicit retrieved labels and priors | Exact selected record order, fragments and other components | Matched manuscript design |
| A / D | Verification stage | Exact generation response, rules and normalization snapshot | Same-generation design |
| R0 / R8 / R14 | Adaptive or fixed exemplar count | Corpus, backend, nonhistory components, references | Manuscript retrieval-budget design |
| RULES_ONLY | Model calls absent | Current input and example rulebook | Named practical baseline; rules are illustrative |
| LLM_ONLY | Retrieval, anatomy context, rules and verification absent | Current findings and generation schema | Named practical baseline, not B |
| TEXT_RAG | Lexical findings retrieval and unverified generation | Same corpus and bounded excerpts | Named practical baseline; details illustrative |
| LEXICAL_VERIFICATION | Local lexical check instead of LLM verifier | A generation | Named control; check rules illustrative |
| SELF_REVIEW | Same-service draft review | A generation and current findings | Named control; not independent expert review |
| COUNT_MATCHED_GATING | Seeded nonsemantic suppression | A generation and A retained count | Output-count-matched control |
| ID_ONLY | Disable name fallback | A generation; same reviewed ontology | Additional mechanistic ablation |
| CF_LABELS | Deterministic cyclic reassignment of historical labels | Selected fragments/order and current findings | Offline extension of a future direction |

Fixed budgets are capped by the number of eligible unique historical groups. When fewer than eight or fourteen are available, the actual number is recorded; records are never duplicated or padded.

R0 is an alias of A and performs no new call. If an entry depends on A, A is generated inside the same execution graph when needed. In a run requesting only D, its prerequisite A is evaluated internally, but D never triggers another generation. `calls_this_arm` excludes prerequisite calls. For a direct A/D comparison, request both in the same run.

The registry validates A/B/C nonhistory equality and rejects accidental changes to verification or rules under those labels. It also detects missing or cyclic dependencies. New policies should use new names rather than repurposing matched-arm labels.

## Human template comparison

No code can synthesize a human-authored baseline or independent clinical rating. Supply real human reports and assessments through a locally governed collection process. The evaluation package accepts independent acceptability annotations and reader/case records; it never creates them from a model's own verdict.

A reader table has columns `reader_id`, `case_id`, `condition`, `acceptable` and `active_seconds`. Missing values remain null. `statistics.crossed_reader` estimates mean paired quality difference and median paired time difference using separate reader and case resampling. Experiment sequence allocation, informed consent, reader qualifications and event collection are study procedures outside this algorithm reference.

## Comparisons that are not implemented as archived experiments

The complete list of ten original control configurations, learned dense/graph retrieval, exact Q/V/D setting changes and production provider manifests were not supplied at executable detail. No public configuration is labeled as having produced a particular reported effect. Counterfactual testing is explicitly an extension, not an observed validation in this release.

## Practical entry points

```bash
python experiments/01_full_history.py --resource runs/resource
python experiments/02_no_history.py --resource runs/resource
python experiments/03_findings_only.py --resource runs/resource
python experiments/04_preverification.py --resource runs/resource
python experiments/05_fixed_eight.py --resource runs/resource
python experiments/06_fixed_fourteen.py --resource runs/resource
python experiments/07_rules_only.py --resource runs/resource
python experiments/08_llm_only.py --resource runs/resource
python experiments/09_text_rag.py --resource runs/resource
python experiments/10_lexical_verification.py --resource runs/resource
python experiments/11_self_review.py --resource runs/resource
python experiments/12_count_matched_gating.py --resource runs/resource
python experiments/13_identifier_only.py --resource runs/resource
python experiments/14_counterfactual_labels.py --resource runs/resource
```

Use `--backend configs/backend_http.yaml --allow-remote` only for an authorized provider. Defaults use the offline fixture. Custom real-data configurations must replace the demonstration vocabulary and rules before research execution.
