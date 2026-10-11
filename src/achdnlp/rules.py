import re
from dataclasses import dataclass
from pathlib import Path

from .config import load_yaml
from .io import digest
from .schema import Anatomy, Quote, RawCandidate, Relation, Sentence
from .text import qualification


@dataclass(frozen=True)
class Support:
    status: str
    evidence: tuple[Quote, ...]


class RuleEngine:
    def __init__(self, path: Path):
        data = load_yaml(path)
        self.fingerprint = digest(data)
        self.version = data["version"]
        self.entities = {
            name: [re.compile(pattern, re.I) for pattern in patterns]
            for name, patterns in data["entities"].items()
        }
        self.relations = [(item, re.compile(item["pattern"], re.I)) for item in data["relations"]]
        self.rules = {
            item["concept_id"]: (item, [re.compile(p, re.I) for p in item.get("patterns", [])])
            for item in data["diagnoses"]
        }

    def anatomy(self, current: list[Sentence]) -> Anatomy:
        entities = set()
        relations = []
        measurements = []
        for sentence in current:
            entities.update(name for name, patterns in self.entities.items()
                            if any(p.search(sentence.text) for p in patterns))
            certainty, temporal, polarity = qualification(sentence.text)
            for item, pattern in self.relations:
                if pattern.search(sentence.text):
                    relations.append(Relation(
                        subject=item["subject"], predicate=item["predicate"], object=item["object"],
                        sentence_id=sentence.sentence_id, certainty=certainty,
                        temporal=temporal, polarity=polarity,
                    ))
            for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(mm|cm|毫米|厘米|%)", sentence.text, re.I):
                measurements.append({"value": float(match[1]), "unit": match[2].lower(),
                                     "sentence_id": sentence.sentence_id, "text": match[0]})
        return Anatomy(entities=sorted(entities), relations=relations, measurements=measurements)

    def support(self, concept_id: str, current: list[Sentence], *, lexical: bool = False) -> Support:
        if concept_id not in self.rules:
            return Support("absent", ())
        rule, patterns = self.rules[concept_id]
        findings: list[tuple[str, Quote]] = []
        for sentence in current:
            if any(pattern.search(sentence.text) for pattern in patterns):
                certainty, temporal, polarity = qualification(sentence.text)
                state = ("negated" if polarity == "negated" else
                         "historical" if temporal == "historical" else certainty)
                findings.append((state, Quote(sentence_id=sentence.sentence_id, text=sentence.text)))
        required = rule.get("requires_relations", [])
        if required and not lexical:
            anatomy = self.anatomy(current)
            relations = [r for r in anatomy.relations
                         if r.polarity == "affirmative" and r.temporal == "current"]
            keys = {r.key for r in relations if r.certainty == "definite"}
            if set(required) <= keys:
                ids = {r.sentence_id for r in relations if r.key in required}
                findings.extend(("definite", Quote(sentence_id=s.sentence_id, text=s.text))
                                for s in current if s.sentence_id in ids)
        states = {state for state, _ in findings}
        if "negated" in states and states & {"definite", "possible"}:
            return Support("conflict", tuple(q for _, q in findings))
        for state in ("definite", "possible", "negated", "historical"):
            if state in states:
                return Support(state, tuple(q for status, q in findings if status == state))
        return Support("absent", ())

    def hypotheses(self, current: list[Sentence], concepts) -> list[RawCandidate]:
        result = []
        for code in self.rules:
            support = self.support(code, current)
            if support.status not in {"definite", "possible"} or code not in concepts:
                continue
            result.append(RawCandidate(identifier=code, name=concepts[code].name,
                                       certainty=support.status, evidence=list(support.evidence)))
        return result
