from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Certainty = Literal["definite", "possible", "unresolved"]
Disposition = Literal["definite", "possible", "unresolved", "rejected", "historical", "internal"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True)


class Query(Model):
    record_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_.-]+$")
    findings: str = Field(min_length=1, max_length=100000)
    modality: str | None = None
    cohort: str = "unspecified"

    @field_validator("findings")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("findings must contain text")
        return value


class HistoricalRecord(Query):
    expert_labels: list[str] = Field(min_length=1)
    source: str = "local"


class Sentence(Model):
    sentence_id: str
    text: str
    start: int
    end: int


class Quote(Model):
    sentence_id: str
    text: str = Field(min_length=1)


class Relation(Model):
    subject: str
    predicate: str
    object: str
    sentence_id: str
    certainty: Certainty = "definite"
    temporal: Literal["current", "historical"] = "current"
    polarity: Literal["affirmative", "negated"] = "affirmative"

    @property
    def key(self) -> str:
        return f"{self.subject}|{self.predicate}|{self.object}"


class Anatomy(Model):
    entities: list[str] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    measurements: list[dict] = Field(default_factory=list)

    def tokens(self) -> set[str]:
        result = {f"entity:{value}" for value in self.entities}
        result.update(
            f"rel:{r.key}:{r.certainty}:{r.temporal}:{r.polarity}" for r in self.relations
        )
        return result


class ResourceRecord(Model):
    record_id: str
    group_id: str
    findings: str
    sentences: list[Sentence]
    anatomy: Anatomy
    modality: str | None
    expert_labels: list[str]
    source: str


class RetrievedCase(Model):
    record_id: str
    group_id: str
    score: float
    rank: int
    channels: dict[str, float | None]
    fragment: str
    expert_labels: list[str]


class RawCandidate(Model):
    identifier: str | None = None
    name: str = Field(min_length=1, max_length=500)
    certainty: Certainty = "unresolved"
    temporal: Literal["current", "historical"] = "current"
    polarity: Literal["affirmative", "negated"] = "affirmative"
    evidence: list[Quote] = Field(default_factory=list)


class Generation(Model):
    diagnoses: list[RawCandidate] = Field(default_factory=list, max_length=128)
    differential: list[RawCandidate] = Field(default_factory=list, max_length=128)


class Candidate(Model):
    candidate_id: str
    concept_id: str | None
    name: str
    order: int
    initial_certainty: Certainty
    temporal: Literal["current", "historical"]
    polarity: Literal["affirmative", "negated"]
    sources: list[str]
    raw_positions: list[int] = Field(default_factory=list)
    resolution: str
    evidence: list[Quote] = Field(default_factory=list)
    state: Disposition = "unresolved"
    decision: str = "not_verified"


class Verdict(Model):
    candidate_id: str
    status: Literal["supported", "uncertain", "unsupported", "historical"]
    evidence: list[Quote] = Field(default_factory=list)
    reason: str = Field(default="", max_length=1000)


class Verification(Model):
    verdicts: list[Verdict]


class CaseResult(Model):
    record_id: str
    cohort: str
    arm: str
    status: Literal["completed", "technical_failure"]
    predictions: list[Candidate] = Field(default_factory=list)
    generation: Generation | None = None
    retrieval: list[RetrievedCase] = Field(default_factory=list)
    audit: dict = Field(default_factory=dict)
    error: str | None = None
    parent_arm: str | None = None
    requires_clinician_review: bool = True


class ClinicalReference(Model):
    record_id: str
    diagnoses: list[str] | None
    supportable: list[str] | None = None
    necessary: list[str] | None = None
    acceptability: dict[str, bool | None] = Field(default_factory=dict)
