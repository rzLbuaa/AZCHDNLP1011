# Reproducibility and execution artifacts

A run directory contains:

- `manifest.json`: code, input/resource/ontology/rule hashes, experiment settings, backend identity, prompt definitions through the code hash, Python and dependency versions.
- `prompts/`: system prompts used by the public implementation, without patient content.
- `records/<id>.json`: per-report atomic checkpoint, local evidence trace, parent-generation hash, result hash and successful-call metadata.
- `predictions.jsonl`: combined typed outputs, rebuilt from checkpoints.
- `completion.json`: technical completion counts, not clinical accuracy.

A process-level file lock prevents simultaneous writers. Resumption requires identical manifest identity and validates record hashes. Configuration or code changes require a new directory. Failed records are retained; this release deliberately does not retry completed checkpoints under a new policy. To repeat a failed experiment, start a separately named run and preserve the first run's denominator.

The API key value is absent from identity and checkpoint files, so credential rotation alone does not change experiment identity. Endpoint and model names are recorded and must not contain user information. HTTP redirects are disabled to avoid inadvertently forwarding authorization or report content to another endpoint. Private proxies are not taken automatically from environment variables; configure an explicitly reviewed transport when needed.

Provider generation is not guaranteed deterministic merely because temperature is zero or a local seed is fixed. The local seed governs sampling controls and bootstrap calculations. A/B/C are input-matched experiments, not claims of independent model errors. A and D share the exact generation object within the run.

## Local verification

```bash
pytest
python -m compileall -q src experiments build_db.py retrieve_generate.py run_ablations.py
python -m achdnlp demo --all-arms --output runs/smoke
python tools/check_release.py
```

`validation/local_validation.json` identifies the environment and checks actually executed when this archive was assembled. Continuous integration is supplied for Linux/Windows and supported Python versions, but a workflow file is not a claim that GitHub CI has already run. The local real-network backend is tested using HTTPX MockTransport; no clinical records or paid provider calls are needed.

## Dependency versions

`requirements-tested.txt` pins the exact locally exercised environment. `pyproject.toml` declares compatible ranges for installation and CI. An index built under a different scikit-learn version is rejected and must be rebuilt. No pickle or untrusted executable serialization is used for the index.
