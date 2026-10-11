# Parameter provenance

The paper specifies an algorithmic design, not every executable constant. This table prevents example settings from being mistaken for archived study settings.

| Element | Manuscript-supported constraint | Public implementation |
|---|---|---|
| Retrieval features | Character TF-IDF, 2–5-grams; anatomy overlap; available descriptors | scikit-learn character analyzer; L2 normalization and sublinear TF are example choices |
| Label separation | Historical labels excluded from retrieval vectors | Findings-only fit; labels joined after selection |
| Retrieval budget | Initially eight, expandable to fourteen; fixed eight/fourteen comparisons | 8/14 preserved |
| Expansion logic | Similarity, margin and complexity influence expansion | 0.45 top-score threshold, 0.035 margin and five relations are example defaults |
| Channel weights | Not fully specified in the supplied manuscript | 0.70 lexical, 0.25 anatomy, 0.05 modality; not fitted clinical weights |
| Missing channels | Omit missing channels from normalization | Pairwise available-channel denominator |
| Descriptors | Available examination descriptors | Modality only; no age or demographic inference |
| Diversity | Limit repeated normalized reports | Cap one record per normalized group; MMR-like lambda 0.85 is an example |
| Relevance floor | Not specified | Findings-based similarity floor 0.01 is an example |
| Excerpts | At most 700 characters per historical finding excerpt | Prefix truncation at 700; the original fragment selector is not recovered |
| Priors | At most 24 aggregate expert-label priors | Similarity-weighted label sum; aggregation formula is an example |
| Ontology | Clinical standard identifiers, names and fallback | Twelve diagnostic concepts plus one internal concept, invented fixture vocabulary |
| Rules | Current anatomy and constraints; high-risk inference restricted | Limited English/Chinese explicit patterns; not the full clinical rules |
| Fallback | Unambiguous recognized wording; no forced nearest label | Exact normalized alias map with conflict rejection |
| Model prompts | Current findings; selected historical findings/labels; separate current-only verification | New inspectable JSON-contract prompts; not archived prompts |
| Model settings | Matched nonhistory components and maximum budgets | Temperature 0, 3000 output tokens and transport limits are example defaults |
| Model identifiers | Eight archived service aliases | Environment variables choose actual approved models; aliases are metadata only |
| Terminal handling | Technical failures retained in denominator | Schema/transport/verifier coverage failures yield explicit failed records |
| Uncertainty | No upward promotion in the audited transition | Definite set is a subset of pre-verification definite candidates |

Outcome labels such as favorable, near-neutral and unfavorable do not define software switches. The exact original Q/V/D run manifests were not supplied; this release does not invent thresholds that would force those outcome directions or clinical counts. The fixed-k comparisons are explicitly defined and separate.

## Source mapping

The source basis is the author-supplied revised main manuscript and supplement. Local source hashes are recorded in `source_manifest.json`; manuscript PDFs and private attachments are not redistributed here.

Main Methods: Expert-case representation and retrieval; Evidence-fragment encapsulation and protected model access; Patient-specific verification and concept tracking; Controlled comparisons and statistical analysis.

Supplement S2: Clinical reference construction, comparison matrix and inference; Controlled retrieval-budget comparison.

Supplement S3: Semantic adjudication and clinical-loss tracking.

Supplement S6–S8: support/necessity, independent reference requirements, reader/case dependence and ordered-output matching.
