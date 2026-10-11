from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .schema import Model


class RetrievalConfig(Model):
    lexical_weight: float = Field(default=0.70, ge=0)
    anatomy_weight: float = Field(default=0.25, ge=0)
    modality_weight: float = Field(default=0.05, ge=0)
    initial_k: int = Field(default=8, ge=1, le=100)
    expanded_k: int = Field(default=14, ge=1, le=100)
    low_similarity: float = Field(default=0.45, ge=0, le=1)
    small_margin: float = Field(default=0.035, ge=0, le=1)
    complex_relations: int = Field(default=5, ge=1)
    min_content_similarity: float = Field(default=0.01, ge=0, le=1)
    diversity_lambda: float = Field(default=0.85, gt=0, le=1)
    max_fragment_chars: int = Field(default=700, ge=32, le=5000)
    max_label_priors: int = Field(default=24, ge=1, le=128)

    @model_validator(mode="after")
    def valid(self):
        if self.lexical_weight + self.anatomy_weight <= 0:
            raise ValueError("at least one findings-based retrieval channel is required")
        if self.initial_k > self.expanded_k:
            raise ValueError("initial_k exceeds expanded_k")
        return self


class StudyConfig(Model):
    ontology: str
    rulebook: str
    seed: int = 2026
    data_kind: Literal["demonstration", "local_research"] = "demonstration"
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


class BackendConfig(Model):
    kind: Literal["demo", "http"] = "demo"
    model_env: str = "ACHDNLP_MODEL"
    base_url_env: str = "ACHDNLP_BASE_URL"
    api_key_env: str = "ACHDNLP_API_KEY"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: int = Field(default=3000, ge=128, le=32000)
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    timeout_seconds: float = Field(default=90, gt=0, le=600)
    attempts: int = Field(default=3, ge=1, le=6)
    json_mode: bool = False
    send_temperature: bool = True
    allow_local_http: bool = False
    archived_alias: str | None = None


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuration must be a mapping")
    return data


def load_study(path: Path) -> StudyConfig:
    config = StudyConfig.model_validate(load_yaml(path))
    for key in ("ontology", "rulebook"):
        value = Path(getattr(config, key))
        setattr(config, key, str((path.parent / value).resolve() if not value.is_absolute() else value))
    return config
