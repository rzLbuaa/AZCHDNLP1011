# Data contract

## Historical records

```json
{"record_id":"H001","findings":"Documented findings only.","expert_labels":["VSD"],"modality":"CTA","source":"local"}
```

`record_id` is a pseudonym, not a hospital identifier. `expert_labels` is a nonempty list of locally approved canonical identifiers or uniquely resolvable names. Labels are validated against the supplied ontology. Free-text impressions are not silently parsed into diagnoses. The source string is local metadata and is not sent to the model.

## Queries

```json
{"record_id":"Q001","findings":"Documented current findings only.","modality":"CTA","cohort":"prospective_cta"}
```

Only declared fields are accepted. Diagnosis columns and reference labels are not part of the query schema. Cohort is an analytical grouping field; it is never placed in a generation or verification payload. No chronological or subject-level identity is inferred from a report ID.

## Independent evaluation references

```json
{"record_id":"Q001","diagnoses":["VSD"],"supportable":["VSD"],"necessary":["VSD"],"acceptability":{"A":true,"B":null}}
```

Null `diagnoses` means unassessed, while an empty list is an assessed empty reference. `supportable` and `necessary` are separate references, and necessary must be a subset of supportable when both are supplied. Acceptability is an independent whole-report rating, not an automatic match test. Codes in evaluation files must already use the same reviewed canonical vocabulary; evaluation does not broaden them to parent families or learn new aliases.

## Predictions and accounting

`CaseResult` contains arm, report ID, technical status, original generation response, ordered predictions, local retrieved-case trace and audit metadata. The audit distinguishes raw objects, normalized candidates, unresolved identifier objects, initial candidate states and final definite candidates. Unknown identifiers retain a review placeholder rather than a fabricated standard code.

The fields `state`, `decision` and `resolution` describe software behavior, not expert correctness. The rendered draft uses only candidate records; it is not a second unchecked generation step. Technical failure remains a separate record. `requires_clinician_review` is true on every output.

## Scoring

Leading-diagnosis concordance uses the first retained diagnostic suggestion, without discarding an unresolved first position. Any-diagnosis coverage is a separate search for at least one affirmative current definite reference match. An unresolved match with no known correct candidate is unscored, not imputed as a success. Failure supplies no assistance and scores zero in the all-input numerator.

With unscored records, the evaluator reports available-case rates, an unscored count and all-input identification bounds; it does not relabel bounds as confidence intervals. Paired A/B tests require the same report set and matching query fingerprints. Missing pairs are counted and not silently imputed.

For concept metrics, support precision and necessary-content retention use separate references and are not merged into a generic F1. F1 is reported only for label-wise TP/FP/FN under one reference definition. The current label table is a code-level illustration; clinical disease-family grouping must be specified in the local ontology and analysis plan.

## Review and time records

`statistics.crossed_reader` consumes real reader/case/condition rows and resamples row/column identities. Time differences are computed inside each reader–case pair; the estimate is not the subtraction of marginal medians. Duplicate cell records are rejected. Quality and time can have different missing-value patterns and denominators.

`statistics.ordinal_paired` consumes a five-by-five joint grade table with rows B and columns A. The sign test evaluates the direction of grade changes, not equality of means. `statistics.rater_agreement` consumes independent pre-consensus binary ratings. Neither function can reconstruct clinical judgments from pipeline state counts.
