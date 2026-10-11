# Release scope and code availability

## Included

This release contains a newly written algorithm reference: resource construction, character TF-IDF retrieval, explicit anatomy features, context encapsulation, structured generation, current-only verification, the named ablation designs, strict output schemas, auditable failure handling, offline examples and statistical functions. It demonstrates the manuscript's information boundaries and comparison logic.

## Not included

The archived clinical application, original fitted retrieval matrices, full clinical ontology, complete expert rules, original prompt text, clinical reports, independent clinical ratings, reader-action logs, actual provider credentials and complete eighteen-configuration execution manifest are not included. Some parameters and module internals are not recoverable from the manuscript. Their example values are listed in `parameter_provenance.md`.

The clinical study and this software release have different validation scopes. The tests in this repository validate the new reference implementation's behavior. They do not revalidate the study, authenticate its source records, or establish clinical safety or effectiveness for this code. No reported clinical success rate is hard-coded into an inference or evaluation path.

## Manuscript code-availability wording

The following wording describes this archive; add the actual repository URL, release tag and persistent identifier only after they exist:

> An executable reference implementation illustrating resource construction, retrieval, evidence-linked generation, verification and the specified ablation designs is available in the accompanying code repository, release 0.1.0. The release includes synthetic test fixtures, experiment configurations, evaluation functions and automated tests. It is not the archived clinical deployment and does not include patient-level data, the complete clinical ontology or the original inference manifests. Example implementation choices are distinguished from manuscript-specified constraints in the repository documentation.

A claim of full computational reproduction would additionally require the corresponding data access, original clinical preprocessing, exact prompts, model/service identifiers, settings and clinical reference records. A polished repository or permissive license alone does not establish that claim.
