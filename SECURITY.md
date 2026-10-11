# Security and data handling

Do not attach clinical reports, credentials, inference payloads, screenshots of patient records or private logs to public issues. Report security concerns through the repository's private security reporting facility when enabled by its maintainers.

This is reference code, not a de-identification or clinical safety product. The local identifier lint catches selected patterns only. All real-data use requires the appropriate institutional authorization and access controls.

Remote inference is disabled until explicitly authorized. Only HTTPS endpoints are accepted by default; local HTTP requires a separate configuration switch. The client validates TLS, disables redirects and does not automatically inherit proxy configuration. Credentials come from environment variables and are excluded from run identity. Result files may contain current-patient quotations and historical excerpts. Keep the complete `runs/` directory private.

Resources use JSON and non-pickled array formats. Hashes detect accidental changes but are not signatures or proof of trusted origin. Do not load artifacts from untrusted sources. Prompts designate report content as data; this reduces accidental instruction mixing but is not a guarantee against prompt injection.

Exact-text overlap checks do not establish patient-level separation. Re-identification risk can remain in findings, measurements and timestamps after direct identifiers have been removed. The clinical resource is not redistributable merely because a code license is permissive.
