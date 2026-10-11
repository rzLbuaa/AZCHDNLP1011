import json

import pytest
from pydantic import ValidationError

from achdnlp.capsule import generation_payload, verification_payload
from achdnlp.config import RetrievalConfig
from achdnlp.evaluation import diagnostic_hits, rate
from achdnlp.ontology import Concept, Ontology
from achdnlp.privacy import check_text
from achdnlp.retrieval import Retriever, overlap, weighted_score
from achdnlp.schema import CaseResult, ClinicalReference, Generation, Quote, RawCandidate, Verdict
from achdnlp.text import normalized, qualification, sentences
from achdnlp.verification import candidates_from, verify_candidates


@pytest.mark.parametrize("text,state", [
    ("No ventricular septal defect", ("definite", "current", "negated")),
    ("Possible ventricular septal defect", ("possible", "current", "affirmative")),
    ("Cannot exclude ventricular septal defect", ("possible", "current", "affirmative")),
    ("室间隔缺损不能排除", ("possible", "current", "affirmative")),
    ("未见房间隔缺损", ("definite", "current", "negated")),
    ("Status post ventricular septal defect repair", ("definite", "historical", "affirmative")),
    ("Residual ventricular septal defect after repair", ("definite", "current", "affirmative")),
])
def test_qualification(text, state):
    assert qualification(text) == state


def test_sentence_offsets_and_decimal():
    text = "  膜部缺损4.5 mm。 Aorta arises from left ventricle. Next clause;末句"
    parts = sentences(text)
    assert len(parts) == 4
    assert "4.5" in parts[0].text
    assert all(text[s.start:s.end] == s.text for s in parts)


@pytest.mark.parametrize("extra", ["reference_labels", "expert_impression", "diagnosis", "影像诊断"])
def test_query_reference_rejected(queries, extra):
    with pytest.raises(ValidationError):
        type(queries[0]).model_validate({**queries[0].model_dump(), extra: "VSD"})


@pytest.mark.parametrize("code,name,expected", [
    ("VSD", "Ventricular septal defect", "VSD"),
    ("unknown", "室间隔缺损", "VSD"),
    (None, "房间隔缺损", "ASD"),
    ("VSD", "房间隔缺损", None),
    ("unknown", "unspecified complex anatomy", None),
])
def test_resolution(ontology, code, name, expected):
    assert ontology.resolve(code, name).concept_id == expected


def test_identifier_only(ontology):
    assert ontology.resolve("unknown", "室间隔缺损", fallback=False).concept_id is None


def test_ambiguous_name():
    vocabulary = Ontology([Concept(concept_id="X", name="one", aliases=["ambiguous"]),
                           Concept(concept_id="Y", name="two", aliases=["ambiguous"])], "test")
    assert vocabulary.resolve(None, "ambiguous").route == "ambiguous_name"


@pytest.mark.parametrize("text", ["姓名：张某", "patient name: Example", "person@example.com", "住院号: 1234"])
def test_privacy_lint(text):
    with pytest.raises(ValueError, match="direct identifier"):
        check_text(text)


def test_missing_channel_renormalization():
    assert weighted_score({"l": 0.5, "a": None, "m": 1.0}, {"l": 0.7, "a": 0.25, "m": 0.05}) == pytest.approx(0.4 / 0.75)
    assert overlap(set(), {"x"}) is None
    assert overlap({"a"}, {"b"}) == 0


def test_spatial_position_not_connection(rules, ontology):
    current = sentences("The aorta lies anterior and right. Both ventricles are seen.")
    assert rules.support("TGA", current).status == "absent"
    assert all(h.identifier != "TGA" for h in rules.hypotheses(current, ontology.concepts))


def test_tga_requires_both_connections(rules):
    assert rules.support("TGA", sentences("The aorta arises from the right ventricle.")).status == "absent"
    assert rules.support("TGA", sentences("The aorta arises from the right ventricle. The pulmonary artery arises from the left ventricle.")).status == "definite"


def test_retrieval_excludes_duplicates_self_and_labels(resource, rules, queries):
    query = queries[0]
    retriever = Retriever(resource, RetrievalConfig())
    results = retriever.retrieve(query, rules.anatomy(sentences(query.findings)), fixed_k=14)
    assert results and len(results) <= 14
    assert len({r.group_id for r in results}) == len(results)
    assert all(len(r.fragment) <= 700 for r in results)
    before = [(r.record_id, r.score) for r in results]
    for record in resource.records:
        record.expert_labels = ["CORONARY_ANOMALY"]
    after = retriever.retrieve(query, rules.anatomy(sentences(query.findings)), fixed_k=14)
    assert [(r.record_id, r.score) for r in after] == before


def test_zero_content_does_not_retrieve_by_modality(resource, rules, queries):
    query = queries[0].model_copy(update={"findings": "zzzzzzzz"})
    results = Retriever(resource, RetrievalConfig()).retrieve(query, rules.anatomy(sentences(query.findings)))
    assert results == []


def test_capsule_limits_and_no_verifier_history(pipeline, queries, ontology, rules):
    current = sentences(queries[0].findings)
    anatomy = rules.anatomy(current)
    history = pipeline.retriever.retrieve(queries[0], anatomy)
    payload = generation_payload(current, anatomy, history, ontology.concepts, labels=False)
    assert payload["label_priors"] == []
    assert all("expert_labels" not in item for item in payload["historical_exemplars"])
    result = pipeline.process(queries[0], ["A"])["A"]
    v = verification_payload(current, result.predictions)
    assert set(v) == {"current_findings", "candidates"}
    assert "source" not in json.dumps(v)
    assert "historical_exemplars" not in json.dumps(v)


def test_unknown_first_not_promoted(ontology):
    generation = Generation(diagnoses=[RawCandidate(identifier="BAD", name="unmapped", certainty="definite"),
                                        RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="definite")])
    items = candidates_from(generation, [], ontology)
    result = CaseResult(record_id="Q", arm="A", cohort="test", status="completed", predictions=items)
    assert diagnostic_hits(result, ClinicalReference(record_id="Q", diagnoses=["VSD"])) == (None, 1)
    assert rate([None, 1, 0])["all_input_rate"] is None


def test_no_three_diagnosis_cap(ontology):
    raw = [RawCandidate(identifier=code, name=ontology.concepts[code].name, certainty="definite")
           for code in ["ASD", "VSD", "PDA", "PS", "COA"]]
    assert len(candidates_from(Generation(diagnoses=raw), [], ontology)) == 5


def test_initial_uncertainty_preserved(ontology, rules):
    current = sentences("Ventricular septal defect is present.")
    raw = RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="possible")
    items = candidates_from(Generation(diagnoses=[raw]), [], ontology)
    verdict = Verdict(candidate_id=items[0].candidate_id, status="supported",
                      evidence=[Quote(sentence_id="S1", text=current[0].text)])
    after = verify_candidates(items, current, ontology, rules, [verdict])
    assert after[0].state == "possible"


def test_negation_overrides_model(ontology, rules):
    current = sentences("No ventricular septal defect.")
    raw = RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="definite")
    items = candidates_from(Generation(diagnoses=[raw]), [], ontology)
    after = verify_candidates(items, current, ontology, rules,
                              [Verdict(candidate_id="C001", status="supported")])
    assert after[0].state == "rejected"


def test_history_quote_not_current_support(ontology, rules):
    current = sentences("A focal ventricular feature is described.")
    raw = RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="definite")
    items = candidates_from(Generation(diagnoses=[raw]), [], ontology)
    after = verify_candidates(items, current, ontology, rules,
                              [Verdict(candidate_id="C001", status="supported",
                                       evidence=[Quote(sentence_id="H1", text=current[0].text)])])
    assert after[0].state == "unresolved"


def test_high_risk_requires_specific_current_support(ontology, rules):
    current = sentences("The aorta lies anterior and right.")
    raw = RawCandidate(identifier="TGA", name=ontology.concepts["TGA"].name, certainty="definite")
    items = candidates_from(Generation(diagnoses=[raw]), [], ontology)
    after = verify_candidates(items, current, ontology, rules,
                              [Verdict(candidate_id="C001", status="supported",
                                       evidence=[Quote(sentence_id="S1", text=current[0].text)])])
    assert after[0].state == "unresolved"


def test_duplicate_sources_merge(ontology):
    raw = RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="definite")
    items = candidates_from(Generation(diagnoses=[raw], differential=[raw]), [raw], ontology)
    assert len(items) == 1
    assert set(items[0].sources) == {"diagnosis", "differential", "rule"}
    assert items[0].raw_positions == [0, 1]


def test_verifier_complete_coverage(ontology, rules):
    raw = RawCandidate(identifier="VSD", name="Ventricular septal defect", certainty="definite")
    items = candidates_from(Generation(diagnoses=[raw]), [], ontology)
    with pytest.raises(ValueError, match="exactly one"):
        verify_candidates(items, sentences("VSD"), ontology, rules, [])


def test_no_label_based_vectorizer_fit(resource):
    analyzer = resource.vectorizer.build_analyzer()
    texts = [normalized(row.findings) for row in resource.records]
    expected = set().union(*(set(analyzer(text)) for text in texts))
    assert set(resource.vectorizer.vocabulary_) <= expected
    assert resource.manifest["index_inputs"] == ["findings"]


def test_concept_parent_validation():
    with pytest.raises(ValueError):
        Ontology([Concept(concept_id="X", name="x", parent="absent")], "test")
