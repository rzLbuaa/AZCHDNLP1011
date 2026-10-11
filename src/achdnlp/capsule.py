from collections import defaultdict
from importlib.resources import files

from .schema import Anatomy, Candidate, RetrievedCase, Sentence


def prompt(name: str) -> str:
    return files("achdnlp").joinpath("prompts", name + ".txt").read_text(encoding="utf-8")


def generation_payload(current: list[Sentence], anatomy: Anatomy, history: list[RetrievedCase],
                       concepts, *, labels: bool = True, include_anatomy: bool = True,
                       max_priors: int = 24) -> dict:
    exemplars, prior = [], defaultdict(float)
    for item in history:
        entry = {"evidence_id": f"H{item.rank}", "fragment": item.fragment,
                 "rank": item.rank, "similarity": item.score}
        if labels:
            entry["expert_labels"] = item.expert_labels
            for code in item.expert_labels:
                prior[code] += max(item.score, 0)
        exemplars.append(entry)
    ordered = sorted(prior.items(), key=lambda x: (-x[1], x[0]))[:max_priors]
    return {
        "current_findings": [s.model_dump(include={"sentence_id", "text"}) for s in current],
        "current_anatomy": anatomy.model_dump() if include_anatomy else None,
        "historical_exemplars": exemplars,
        "label_priors": [{"identifier": code, "weight": weight} for code, weight in ordered],
        "allowed_concepts": [{"identifier": c.concept_id, "name": c.name}
                             for c in concepts.values() if c.kind == "diagnostic"],
    }


def verification_payload(current: list[Sentence], candidates: list[Candidate]) -> dict:
    return {
        "current_findings": [s.model_dump(include={"sentence_id", "text"}) for s in current],
        "candidates": [{"candidate_id": c.candidate_id, "identifier": c.concept_id,
                        "name": c.name, "initial_certainty": c.initial_certainty,
                        "temporal": c.temporal, "polarity": c.polarity} for c in candidates],
    }
