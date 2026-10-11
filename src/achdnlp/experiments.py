from pathlib import Path
from typing import Literal

from pydantic import Field

from .config import load_yaml
from .schema import Model


class Arm(Model):
    name: str
    history: Literal["full", "findings", "none"] = "full"
    retrieval: Literal["hybrid", "lexical"] = "hybrid"
    fixed_k: int | None = Field(default=None, ge=1, le=100)
    anatomy_to_generator: bool = True
    supplement_rules: bool = True
    verification: Literal["llm", "none", "lexical", "self_review"] = "llm"
    fallback: bool = True
    rule_only: bool = False
    source_arm: str | None = None
    count_matched: bool = False
    reuse_final: bool = False
    counterfactual_labels: bool = False


def load_arms(path: Path) -> dict[str, Arm]:
    config = load_yaml(path)
    arms = [Arm.model_validate(row) for row in config["arms"]]
    lookup = {arm.name: arm for arm in arms}
    if len(arms) != len(lookup):
        raise ValueError("duplicate arm names")
    for arm in arms:
        if arm.source_arm and arm.source_arm not in lookup:
            raise ValueError("source arm does not exist")
        seen = {arm.name}
        cursor = arm
        while cursor.source_arm:
            if cursor.source_arm in seen:
                raise ValueError("cyclic arm dependencies")
            seen.add(cursor.source_arm)
            cursor = lookup[cursor.source_arm]
    if {"A", "B", "C", "D"} <= lookup.keys():
        a, b, c, d = (lookup[key] for key in ("A", "B", "C", "D"))
        base = a.model_dump(exclude={"name", "history"})
        if b.history != "none" or c.history != "findings" or a.history != "full":
            raise ValueError("A/B/C historical input contract violated")
        if b.model_dump(exclude={"name", "history"}) != base or c.model_dump(exclude={"name", "history"}) != base:
            raise ValueError("A/B/C must differ only in historical input")
        if d.source_arm != "A" or d.verification != "none":
            raise ValueError("D must reuse A generation without verification")
    return lookup
