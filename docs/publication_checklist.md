# Publication-facing release checks

This list concerns the release, not the clinical results.

1. Confirm redistribution rights and the selected MIT license with the code rightsholders. Do not copy private dependencies or third-party datasets into the archive.
2. Publish an actual versioned release and archive that version when a persistent identifier is available. Do not invent a repository address, DOI, accepted-paper citation or archived commit.
3. Keep real clinical reports, references, predictions, evidence quotations, credentials and model-response caches outside version control. Synthetic fixtures are explicitly identified as such.
4. Use the code-availability wording in `release_scope.md` only to describe the reference code actually provided. The study's restricted data-access statement remains separate.
5. Inspect source-to-code mapping and example parameter disclosures. Do not identify the new prompts or toy rulebook as the original clinical runtime.
6. Preserve the actual preparation history in journal disclosures. Code style and minimal comments do not waive a journal's disclosure requirements for assistance with writing code, processing data or preparing text.
7. Populate repository author/contributor and citation metadata with the actual release contributors. The current CITATION file names the project contributor group and the paper as unpublished context, without assigning individual code contributions.
8. Execute local tests and CI under the intended environment, verify real provider contracts on approved nonclinical inputs, and retain the resulting logs locally.

## Primary sources checked

- JAMIA, Instructions to authors, authorship/AI use and data archiving: https://academic.oup.com/jamia/pages/General_Instructions
- GitHub, About CITATION files: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files
- GitHub, Licensing a repository: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository

Accessed 11 October 2026. This checklist is not a certification of regulatory or institutional compliance.
