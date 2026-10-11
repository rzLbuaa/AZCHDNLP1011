import numpy as np

from .config import RetrievalConfig
from .io import digest
from .resource import Resource
from .schema import Anatomy, Query, RetrievedCase
from .text import normalized


def overlap(left: set[str], right: set[str]) -> float | None:
    if not left or not right:
        return None
    return len(left & right) / len(left | right)


def weighted_score(channels: dict[str, float | None], weights: dict[str, float]) -> float:
    usable = [(value, weights[name]) for name, value in channels.items()
              if value is not None and weights[name] > 0]
    denominator = sum(weight for _, weight in usable)
    return sum(value * weight for value, weight in usable) / denominator if denominator else 0.0


class Retriever:
    def __init__(self, resource: Resource, config: RetrievalConfig):
        self.resource, self.config = resource, config

    def retrieve(self, query: Query, anatomy: Anatomy, *, fixed_k: int | None = None,
                 lexical_only: bool = False) -> list[RetrievedCase]:
        cfg = self.config
        vector = self.resource.vectorizer.transform([normalized(query.findings)])
        lexical = (self.resource.matrix @ vector.T).toarray().ravel()
        weights = {"lexical": 1.0 if lexical_only else cfg.lexical_weight,
                   "anatomy": 0.0 if lexical_only else cfg.anatomy_weight,
                   "modality": 0.0 if lexical_only else cfg.modality_weight}
        query_group = digest(normalized(query.findings))
        scored = []
        query_tokens = anatomy.tokens()
        for i, row in enumerate(self.resource.records):
            if row.group_id == query_group or row.record_id == query.record_id:
                continue
            structural = overlap(query_tokens, row.anatomy.tokens())
            channels = {
                "lexical": float(lexical[i]) if vector.nnz else None,
                "anatomy": structural,
                "modality": (float(query.modality.casefold() == row.modality.casefold())
                             if query.modality and row.modality else None),
            }
            content = max(lexical[i] if weights["lexical"] else 0.0,
                          (structural or 0.0) if weights["anatomy"] else 0.0)
            if content <= 0 or content < cfg.min_content_similarity:
                continue
            score = weighted_score(channels, weights)
            scored.append((i, score, channels))
        scored.sort(key=lambda x: (-x[1], self.resource.records[x[0]].record_id))
        if not scored:
            return []
        margin = scored[0][1] - (scored[1][1] if len(scored) > 1 else 0)
        expand = (scored[0][1] < cfg.low_similarity or margin < cfg.small_margin or
                  len(anatomy.relations) >= cfg.complex_relations)
        target = fixed_k or (cfg.expanded_k if expand else cfg.initial_k)
        selected, groups = [], set()
        remaining = scored.copy()
        redundancy = np.zeros(len(self.resource.records), dtype=float)
        while remaining and len(selected) < target:
            best = None
            best_value = -np.inf
            for entry in remaining:
                i, score, _ = entry
                row = self.resource.records[i]
                if row.group_id in groups:
                    continue
                value = cfg.diversity_lambda * score - (1 - cfg.diversity_lambda) * redundancy[i]
                if value > best_value:
                    best, best_value = entry, value
            if best is None:
                break
            selected.append(best)
            groups.add(self.resource.records[best[0]].group_id)
            similarities = (self.resource.matrix @ self.resource.matrix[best[0]].T).toarray().ravel()
            redundancy = np.maximum(redundancy, similarities)
            remaining = [entry for entry in remaining if entry[0] != best[0]]
        output = []
        for rank, (i, score, channels) in enumerate(selected, 1):
            row = self.resource.records[i]
            output.append(RetrievedCase(
                record_id=row.record_id, group_id=row.group_id, score=score, rank=rank,
                channels=channels, fragment=row.findings[:cfg.max_fragment_chars],
                expert_labels=row.expert_labels,
            ))
        return output
