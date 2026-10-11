import numpy as np
import pytest

from achdnlp.evaluation import diagnostic_hits, evaluate, rate
from achdnlp.schema import CaseResult, ClinicalReference
from achdnlp.statistics import (cluster_ratio, crossed_reader, label_metrics,
                               ordinal_paired, paired_binary, rater_agreement, wilson)


@pytest.mark.parametrize("hits,n", [(0, 0), (0, 10), (10, 10), (7, 10), (1, 1)])
def test_wilson_boundaries(hits, n):
    interval = wilson(hits, n)
    if n:
        assert 0 <= interval[0] <= interval[1] <= 1
        assert interval[0] - 1e-12 <= hits / n <= interval[1] + 1e-12
    else:
        assert interval is None


def test_invalid_wilson():
    with pytest.raises(ValueError):
        wilson(11, 10)


def test_exact_paired_symmetry():
    a = paired_binary([7, 3, 1, 2], resamples=1000)
    b = paired_binary([7, 1, 3, 2], resamples=1000)
    assert a["p_exact"] == b["p_exact"]
    assert a["difference"] == -b["difference"]
    assert paired_binary([8, 0, 0, 2], resamples=100)["p_exact"] == 1


def test_invalid_paired_counts():
    with pytest.raises(ValueError):
        paired_binary([1, -1, 2, 3])
    assert paired_binary([0, 0, 0, 0])["difference"] is None


def test_missing_not_failure():
    result = CaseResult(record_id="Q", cohort="test", arm="A", status="completed")
    assert diagnostic_hits(result, None) == (None, None)
    failed = result.model_copy(update={"status": "technical_failure"})
    assert diagnostic_hits(failed, None) == (0, 0)
    summary = rate([1, 0, None])
    assert summary["identification_bounds"] == [1 / 3, 2 / 3]
    assert summary["all_input_rate"] is None


def test_evaluation_rejects_mismatched_inputs():
    a = CaseResult(record_id="A", cohort="test", arm="A", status="completed", audit={"query_hash": "1"})
    b = CaseResult(record_id="B", cohort="test", arm="B", status="completed", audit={"query_hash": "2"})
    with pytest.raises(ValueError, match="input sets differ"):
        evaluate([a, b], [], resamples=100)


def test_label_metrics_not_support_necessity_f1():
    result = label_metrics(3, 1, 2)
    assert result["precision"] == 0.75
    assert result["recall"] == 0.6
    assert result["f1"] == pytest.approx(6 / 9)
    assert label_metrics(0, 0, 0)["f1"] is None


def test_cluster_bootstrap_denominators():
    result = cluster_ratio([1, 2, 1], [2, 3, 1], resamples=200)
    assert result["estimate"] == pytest.approx(4 / 6)
    assert result["reports"] == 3


def test_crossed_reader_uses_paired_time_not_marginal_medians():
    rows = []
    for i, reader in enumerate(["R1", "R2"]):
        for j, case in enumerate(["Q1", "Q2", "Q3"]):
            rows += [{"reader_id": reader, "case_id": case, "condition": "U", "acceptable": True,
                      "active_seconds": 100 + i * 30 + j * 10},
                     {"reader_id": reader, "case_id": case, "condition": "V", "acceptable": True,
                      "active_seconds": 90 + i * 30 + j * 10}]
    result = crossed_reader(rows, "U", "V", resamples=200)
    assert result["time_difference"] == -10
    assert result["time_ci95"] == [-10, -10]
    assert result["readers"] == 2 and result["cases"] == 3 and result["time_pairs"] == 6
    with pytest.raises(ValueError, match="duplicate"):
        crossed_reader(rows + [rows[0]], "U", "V", resamples=200)


def test_ordinal_counts_and_test_estimand():
    matrix = np.eye(5, dtype=int) * 2
    matrix[2, 4] += 3
    result = ordinal_paired(matrix, resamples=200)
    assert result["A_higher"] == 3 and result["A_lower"] == 0 and result["tied"] == 10
    assert result["mean_difference"] == pytest.approx(6 / 13)
    assert result["sign_test_p"] == 0.25


def test_kappa_from_independent_ratings():
    ratings = [[1, 1, 1], [0, 0, 0], [1, 1, 0], [0, 0, 0]]
    result = rater_agreement(ratings, resamples=200)
    assert result["cohen_pairwise"]["1-2"] == 1.0
    assert result["fleiss_kappa"] < 1
    assert result["unanimous_fraction"] == 0.75


def test_unassessed_whole_report_not_derived_from_diagnostic_hit():
    result = CaseResult(record_id="Q", cohort="test", arm="A", status="completed")
    metrics = evaluate([result], [ClinicalReference(record_id="Q", diagnoses=[])], resamples=100)
    assert metrics["arms"]["A"]["whole_report_acceptability"]["unscored_n"] == 1
