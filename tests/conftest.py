from pathlib import Path

import pytest

from achdnlp.backend import DemoBackend
from achdnlp.config import load_study
from achdnlp.experiments import load_arms
from achdnlp.io import read_jsonl
from achdnlp.ontology import Ontology
from achdnlp.pipeline import Pipeline
from achdnlp.resource import Resource, build_resource
from achdnlp.rules import RuleEngine
from achdnlp.schema import Query

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project():
    return ROOT


@pytest.fixture
def study(project):
    return load_study(project / "configs/study.yaml")


@pytest.fixture
def ontology(study):
    return Ontology.load(Path(study.ontology))


@pytest.fixture
def rules(study):
    return RuleEngine(Path(study.rulebook))


@pytest.fixture
def resource(tmp_path, project, ontology, rules):
    path = tmp_path / "resource"
    build_resource(project / "data/demo/history.jsonl", path, ontology, rules)
    return Resource.load(path, ontology, rules)


@pytest.fixture
def queries(project):
    return read_jsonl(project / "data/demo/queries.jsonl", Query)


@pytest.fixture
def pipeline(resource, ontology, rules, study, project):
    return Pipeline(resource, ontology, rules, DemoBackend(ontology, rules), study,
                    load_arms(project / "configs/experiments.yaml"))
