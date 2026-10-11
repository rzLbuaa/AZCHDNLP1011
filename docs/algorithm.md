# Algorithm and information boundaries

## 1. Resource construction

An input record contains findings, normalized historical expert labels, a pseudonymous record ID and optional modality/source fields. Findings are segmented into clauses with offsets. Explicit anatomical mentions, directed relations and measurements retain sentence references and certainty/temporal qualifiers. Normalized findings determine duplicate groups.

A character 2–5-gram TF-IDF vectorizer is fitted on findings alone. The index contains a CSR matrix, vocabulary and IDF array. JSON and NPZ/NPY artifacts are used; no executable pickle is loaded. A manifest binds data, ontology, rulebook, artifact hashes and the scikit-learn version. A loaded index is not silently refitted on query reports.

The stored historical record contains labels but the retrieval score never uses them. Changing a historical label without changing findings or modality cannot change the ranking. Tests enforce this boundary.

## 2. Retrieval

For query q and record j, the reference implementation uses lexical cosine similarity, Jaccard overlap of explicit anatomical tokens and available modality agreement:

    score(q,j) = sum(w[c] * s[c](q,j), c available) / sum(w[c], c available)

An absent anatomy or modality channel is omitted from the denominator. An available but disjoint anatomy channel is a zero, not missing. At least one findings-derived channel must exceed the example content floor; modality alone cannot retrieve a record.

The baseline selects eight exemplars and may expand to fourteen when similarity is low, the top-score margin is small, or the query has many explicit relations. The numeric trigger values are example choices, not manuscript-recovered parameters. A greedy relevance-minus-redundancy score and a one-record-per-normalized-group constraint limit repeated context. Query-record identity and exact normalized-text matches are excluded. Whole-run input overlap is rejected before inference; this is not a patient-level leakage guarantee.

Excerpt selection is deliberately simple: a prefix bounded at 700 characters. A more sophisticated evidence selector can replace this function without changing A/B/C controls. Truncation is recorded by the bounded fragment and does not imply that every historical finding was supplied.

## 3. Evidence capsule

The generator sees numbered current findings, current anatomy, selected historical fragments, retrieval rank/score and, in A, explicit labels and up to 24 aggregate label priors. Historical record IDs and source paths are replaced by local H1/H2 tokens in model-facing input. The local trace retains the mapping.

C preserves the selected fragments and order while removing labels and aggregate priors. B supplies no historical fragments or priors. Both preserve the same system prompt, parser, current-anatomy representation and downstream verification settings as A. Nonhistory token budgets are identical; shorter prompts are not padded.

JSON encapsulation is an information-boundary representation, not encryption. HTTPS, where used, is transport protection; no authenticated-encryption capsule, clinical privacy certification or complete de-identification mechanism is implemented.

## 4. Candidate formation and identity

Generation returns diagnoses and differential candidates under a strict schema. Canonicalization accepts an existing identifier, or an unambiguous diagnostic name/synonym when fallback is enabled. Conflicts and ambiguous names remain unresolved; there is no nearest-label match or parent-family scoring shortcut.

Repeated occurrences are merged using canonical ID, temporal state and polarity, preserving the first occurrence's order and initial certainty. Rule-only hypotheses are appended, not inserted ahead of model candidates. Sources and raw occurrence positions remain available. Non-diagnostic internal entries are routed separately.

Unknown identifiers remain as review placeholders in the public reference's ordered prediction interface. They are excluded from the normalized-candidate audit count, but they cannot be silently removed to promote a later diagnosis during evaluation. This explicit placeholder interface is a reference-release design choice, not a claim about the historical application's renderer.

## 5. Verification and decision logic

The verifier receives only current sentences and canonical candidate identifiers/names/states. Historical exemplars, label priors and generator evidence/explanations are excluded. The self-review control additionally receives the same draft; it is separately identified.

Local negative, historical and conflicting evidence routes are applied first. A rule/model contradiction remains unresolved. Explicit current-rule support may support a candidate without a valid model quotation, while a model-only support judgment requires a locatable current quote. High-risk concepts require explicit current rule support in this example implementation. Initial uncertainty is never promoted to definite. The definitive set therefore remains a subset of the pre-verification definitive set.

A quote's location is a mechanical property, not an independent clinical correctness test. The model support judgment and small rulebook remain imperfect. The default rulebook uses conservative clause-level cues and limited explicit patterns. It does not implement complete segmental CHD interpretation or infer clinical normality from missing anatomy.

All retained outputs are rendered from the candidate table; unverified model-authored free text is not appended after the check. The display contains definite, possible and unresolved suggestions with evidence IDs. Clinical acceptance, editing and final diagnosis remain external human activities.

## 6. Controlled execution

One per-query execution graph shares A's frozen retrieval and generation snapshots. D returns the pre-verification snapshot without another generation request. A verification failure does not erase an already valid generation snapshot. Lexical, self-review, count-matched and identifier-only controls reuse that snapshot. A/B/C errors are recorded as technical failures rather than patched with a favorable result.

The count-matched control samples the same number of definite candidates retained by A in that report; it never reads true diagnoses or necessary-content annotations. The seed derives from the run seed, record ID and arm. Its purpose is to separate semantic selection from count reduction; it is not calibrated abstention.
