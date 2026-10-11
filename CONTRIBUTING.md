# Contributing

Keep resource construction, generation, verification and evaluation as separate interfaces. New experiments must declare their changed components and reuse shared execution code.

Run the test suite and an offline demonstration before a change is merged. Add a boundary test when changing input schemas, prompt content, candidate order, state transitions or A/B/C/D behavior. Do not update expected clinical outcomes to accommodate a code change; this repository contains no clinical outcome targets.

Use clear names, typed public interfaces and short functions. Prefer explanations in `docs/` over repetitive inline comments. New example thresholds must be identified as reference choices. New domain rules require explicit provenance and separate clinical validation; adding a pattern is not such validation.

Never submit patient data, credentials, source manuscripts containing private disclosures or deployment artifacts. Synthetic test fixtures must be labeled as synthetic and must not be obtained by lightly editing a real clinical record.
