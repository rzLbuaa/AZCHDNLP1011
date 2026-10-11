from copy import deepcopy

from .schema import Candidate, Generation, Quote, Sentence, Verdict
from .text import qualification


def candidates_from(generation: Generation, hypotheses, ontology, *, fallback: bool = True):
    result: list[Candidate] = []
    by_key = {}
    raw = [(item, "diagnosis") for item in generation.diagnoses]
    raw += [(item, "differential") for item in generation.differential]
    raw += [(item, "rule") for item in hypotheses]
    for position, (item, source) in enumerate(raw):
        resolution = ontology.resolve(item.identifier, item.name, fallback)
        code = resolution.concept_id
        key = (code, item.temporal, item.polarity) if code else (None, position)
        if key in by_key:
            existing = result[by_key[key]]
            existing.sources = sorted(set([*existing.sources, source]))
            existing.evidence = unique_quotes([*existing.evidence, *item.evidence])
            if source != "rule":
                existing.raw_positions.append(position)
            continue
        state = item.certainty
        if item.polarity == "negated":
            state = "rejected"
        elif item.temporal == "historical":
            state = "historical"
        elif not code:
            state = "unresolved"
        elif ontology.concepts[code].kind != "diagnostic":
            state = "internal"
        by_key[key] = len(result)
        result.append(Candidate(
            candidate_id=f"C{len(result) + 1:03d}", concept_id=code,
            name=ontology.concepts[code].name if code else item.name,
            order=len(result), initial_certainty=item.certainty,
            temporal=item.temporal, polarity=item.polarity, sources=[source],
            raw_positions=[position] if source != "rule" else [],
            resolution=resolution.route, evidence=list(item.evidence), state=state,
        ))
    return result


def unique_quotes(items: list[Quote]) -> list[Quote]:
    return list({(item.sentence_id, item.text): item for item in items}.values())


def eligible(candidates: list[Candidate]) -> list[Candidate]:
    return [c for c in candidates if c.concept_id and c.state not in {"internal", "historical", "rejected"}]


def valid_quotes(evidence: list[Quote], current: list[Sentence]) -> list[Quote]:
    lookup = {s.sentence_id: s.text for s in current}
    return [q for q in evidence if q.sentence_id in lookup and q.text.strip()
            and q.text in lookup[q.sentence_id]]


def verify_candidates(candidates, current, ontology, rules, verdicts: list[Verdict],
                      *, lexical: bool = False, rule_override: bool = True):
    result = deepcopy(candidates)
    lookup = {v.candidate_id: v for v in verdicts}
    expected = {c.candidate_id for c in eligible(candidates)}
    if not lexical and (len(lookup) != len(verdicts) or set(lookup) != expected):
        raise ValueError("verifier must return exactly one verdict per eligible candidate")
    for candidate in result:
        if candidate.candidate_id not in expected:
            continue
        support = rules.support(candidate.concept_id, current, lexical=lexical)
        verdict = lookup.get(candidate.candidate_id)
        if support.status in {"negated", "historical", "conflict"}:
            candidate.state = {"negated": "rejected", "historical": "historical",
                               "conflict": "unresolved"}[support.status]
            candidate.decision = f"current_evidence_{support.status}"
            candidate.evidence = list(support.evidence)
            continue
        if lexical:
            status = {"definite": "supported", "possible": "uncertain"}.get(support.status, "uncertain")
            quotes = list(support.evidence)
        else:
            status = verdict.status
            quotes = valid_quotes(verdict.evidence, current)
        if status == "historical":
            candidate.state, candidate.decision = "historical", "verifier_historical"
        elif status == "unsupported":
            candidate.state = "unresolved" if support.status == "definite" else "rejected"
            candidate.decision = "rule_model_conflict" if support.status == "definite" else "unsupported"
        elif support.status == "possible":
            candidate.state, candidate.decision = "possible", "current_evidence_uncertain"
        elif rule_override and support.status == "definite":
            candidate.state, candidate.decision = "definite", "explicit_current_rule"
            quotes = list(support.evidence)
        elif ontology.concepts[candidate.concept_id].high_risk:
            candidate.state, candidate.decision = "unresolved", "high_risk_evidence_required"
        elif status == "supported" and quotes and all(
            qualification(q.text)[1:] == ("current", "affirmative") and
            qualification(q.text)[0] == "definite" for q in quotes
        ):
            candidate.state, candidate.decision = "definite", "model_support_with_current_quote"
        else:
            candidate.state, candidate.decision = "unresolved", "insufficient_current_support"
        if candidate.state == "definite" and candidate.initial_certainty != "definite":
            candidate.state = candidate.initial_certainty
            candidate.decision += ":initial_uncertainty_preserved"
        candidate.evidence = quotes
    return result
