from copy import deepcopy

import numpy as np

from .capsule import generation_payload, verification_payload
from .io import digest
from .privacy import check_text
from .schema import CaseResult, Generation, Query
from .text import sentences
from .verification import candidates_from, eligible, verify_candidates


class Pipeline:
    def __init__(self, resource, ontology, rules, backend, config, arms):
        from .retrieval import Retriever
        self.resource, self.ontology, self.rules, self.backend = resource, ontology, rules, backend
        self.config, self.arms = config, arms
        self.retriever = Retriever(resource, config.retrieval)

    def process(self, query: Query, names: list[str]) -> dict[str, CaseResult]:
        check_text(query.findings)
        current = sentences(query.findings)
        anatomy = self.rules.anatomy(current)
        frozen_history = self.retriever.retrieve(query, anatomy)
        completed, snapshots = {}, {}

        def execute(name: str):
            if name in completed:
                return completed[name]
            arm = self.arms[name]
            generation = None
            history = []
            started_calls = len(self.backend.calls)
            try:
                if arm.source_arm:
                    parent = execute(arm.source_arm)
                    started_calls = len(self.backend.calls)
                    if arm.reuse_final:
                        result = parent.model_copy(deep=True, update={"arm": name, "parent_arm": arm.source_arm})
                        result.audit["calls_this_arm"] = 0
                        completed[name] = result
                        return result
                    if arm.source_arm not in snapshots:
                        raise ValueError("parent generation is unavailable")
                    generation, history = deepcopy(snapshots[arm.source_arm])
                elif arm.rule_only:
                    generation = Generation()
                else:
                    if arm.history != "none":
                        if arm.fixed_k or arm.retrieval == "lexical":
                            history = self.retriever.retrieve(query, anatomy, fixed_k=arm.fixed_k,
                                                              lexical_only=arm.retrieval == "lexical")
                        else:
                            history = deepcopy(frozen_history)
                    if arm.counterfactual_labels:
                        codes = sorted(c.concept_id for c in self.ontology.concepts.values()
                                       if c.kind == "diagnostic")
                        for item in history:
                            item.expert_labels = [codes[(codes.index(code) + 1) % len(codes)]
                                                  for code in item.expert_labels]
                    payload = generation_payload(current, anatomy, history, self.ontology.concepts,
                                                 labels=arm.history == "full",
                                                 include_anatomy=arm.anatomy_to_generator,
                                                 max_priors=self.config.retrieval.max_label_priors)
                    generation = self.backend.call("generate", payload)
                snapshots[name] = (deepcopy(generation), deepcopy(history))
                hypotheses = self.rules.hypotheses(current, self.ontology.concepts) if arm.supplement_rules else []
                before = candidates_from(generation, hypotheses, self.ontology, fallback=arm.fallback)
                after = deepcopy(before)
                if arm.verification != "none":
                    selected = eligible(before)
                    if arm.verification == "lexical":
                        after = verify_candidates(before, current, self.ontology, self.rules, [], lexical=True)
                    elif selected:
                        payload = verification_payload(current, selected)
                        stage = "self_review" if arm.verification == "self_review" else "verify"
                        if stage == "self_review":
                            payload["draft"] = generation.model_dump()
                        verification = self.backend.call(stage, payload)
                        after = verify_candidates(before, current, self.ontology, self.rules,
                                                  verification.verdicts, rule_override=arm.supplement_rules)
                if arm.count_matched:
                    parent = completed[arm.source_arm]
                    if parent.status != "completed":
                        raise ValueError("count-matched control requires completed parent verification")
                    target = sum(c.state == "definite" for c in parent.predictions if c.concept_id)
                    pool = [c for c in after if c.state == "definite" and c.concept_id]
                    if target > len(pool):
                        raise ValueError("parent definite count exceeds pre-verification pool")
                    seed = int(digest([self.config.seed, query.record_id, name])[:16], 16)
                    keep = set(np.random.default_rng(seed).choice(len(pool), target, replace=False).tolist())
                    for i, candidate in enumerate(pool):
                        if i not in keep:
                            candidate.state, candidate.decision = "unresolved", "count_matched_suppression"
                after.sort(key=lambda c: c.order)
                audit = {
                    "query_hash": digest(query.model_dump()), "generation_hash": digest(generation.model_dump()),
                    "history_selection_hash": digest([(h.record_id, h.rank, h.fragment) for h in history]),
                    "before": [c.model_dump() for c in before],
                    "raw_objects": len(generation.diagnoses) + len(generation.differential),
                    "normalized_candidates": sum(c.concept_id is not None and c.state != "internal"
                                                 and c.temporal == "current" and c.polarity == "affirmative"
                                                 for c in before),
                    "historical_candidates": sum(c.state == "historical" for c in before),
                    "internal_candidates": sum(c.state == "internal" for c in before),
                    "displayed_normalized": sum(c.concept_id is not None and c.state in
                                                 {"definite", "possible", "unresolved"} for c in after),
                    "unresolved_objects": sum(c.concept_id is None for c in before),
                    "final_definite": sum(c.state == "definite" for c in after),
                    "calls_this_arm": len(self.backend.calls) - started_calls,
                    "data_kind": self.config.data_kind,
                }
                result = CaseResult(record_id=query.record_id, cohort=query.cohort, arm=name,
                                    status="completed", predictions=after, generation=generation,
                                    retrieval=history, audit=audit, parent_arm=arm.source_arm)
            except (ValueError, RuntimeError) as error:
                result = CaseResult(record_id=query.record_id, cohort=query.cohort, arm=name,
                                    status="technical_failure", generation=generation, retrieval=history,
                                    error=f"{type(error).__name__}: {str(error)[:200]}",
                                    parent_arm=arm.source_arm,
                                    audit={"query_hash": digest(query.model_dump()),
                                           "calls_this_arm": len(self.backend.calls) - started_calls,
                                           "data_kind": self.config.data_kind})
            completed[name] = result
            return result

        for name in names:
            if name not in self.arms:
                raise ValueError(f"unknown arm: {name}")
            execute(name)
        return {name: completed[name] for name in names}


def render_draft(result: CaseResult) -> str:
    if result.status != "completed":
        return "No draft available: technical failure."
    lines = []
    for candidate in result.predictions:
        if candidate.state in {"definite", "possible", "unresolved"}:
            citations = ", ".join(dict.fromkeys(q.sentence_id for q in candidate.evidence))
            lines.append(f"{len(lines) + 1}. {candidate.name} [{candidate.state}] ({citations or 'review required'})")
    return "\n".join(lines) or "No diagnostic suggestion. Clinical review is required."
