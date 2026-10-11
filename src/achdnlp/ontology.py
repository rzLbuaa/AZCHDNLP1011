import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from .io import digest
from .schema import Model
from .text import term_key


class Concept(Model):
    concept_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    parent: str | None = None
    kind: str = "diagnostic"
    high_risk: bool = False


@dataclass(frozen=True)
class Resolution:
    concept_id: str | None
    route: str


class Ontology:
    def __init__(self, concepts: list[Concept], version: str):
        self.concepts = {c.concept_id: c for c in concepts}
        if len(self.concepts) != len(concepts):
            raise ValueError("duplicate concept identifiers")
        self.version = version
        self.aliases: dict[str, set[str]] = {}
        for item in concepts:
            for name in [item.concept_id, item.name, *item.aliases]:
                self.aliases.setdefault(term_key(name), set()).add(item.concept_id)
            if item.parent and item.parent not in self.concepts:
                raise ValueError("unknown ontology parent")
        self.fingerprint = digest([c.model_dump() for c in concepts])

    @classmethod
    def load(cls, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([Concept.model_validate(c) for c in data["concepts"]], data["version"])

    def resolve(self, identifier: str | None, name: str, fallback: bool = True) -> Resolution:
        known_id = identifier if identifier in self.concepts else None
        names = self.aliases.get(term_key(name), set()) if name else set()
        if len(names) > 1:
            return Resolution(None, "ambiguous_name")
        name_id = next(iter(names), None)
        if known_id and name_id and known_id != name_id:
            return Resolution(None, "identifier_name_conflict")
        if known_id:
            if name and not name_id:
                return Resolution(None, "unrecognized_name")
            return Resolution(known_id, "identifier")
        if fallback and name_id:
            return Resolution(name_id, "name_fallback")
        return Resolution(None, "unresolved_identifier")

    def normalize_label(self, label: str) -> str:
        resolution = self.resolve(label, label)
        if not resolution.concept_id:
            raise ValueError("unknown or ambiguous expert label; provide a canonical identifier")
        return resolution.concept_id
