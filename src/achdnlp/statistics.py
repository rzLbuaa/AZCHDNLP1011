from statistics import NormalDist

import numpy as np
from scipy.stats import binomtest


def wilson(hits: int, n: int, confidence: float = 0.95) -> tuple[float, float] | None:
    if not 0 <= hits <= n or not 0 < confidence < 1:
        raise ValueError("invalid binomial counts or confidence level")
    if n == 0:
        return None
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    p, z2 = hits / n, z * z
    center = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return float(max(0, center - half)), float(min(1, center + half))


def paired_binary(counts, *, resamples: int = 20000, seed: int = 2026) -> dict:
    values = np.asarray(counts)
    if values.shape != (4,) or not np.all(values >= 0) or not np.all(values == values.astype(int)):
        raise ValueError("four nonnegative integer counts are required")
    if resamples < 100:
        raise ValueError("at least 100 bootstrap resamples are required")
    n = int(values.sum())
    if not n:
        return {"n": 0, "difference": None, "ci95": None, "p_exact": None}
    both, a_only, b_only, neither = (int(v) for v in values)
    samples = np.random.default_rng(seed).multinomial(n, values / n, size=resamples)
    effects = (samples[:, 1] - samples[:, 2]) / n
    p = float(binomtest(a_only, a_only + b_only, 0.5).pvalue) if a_only + b_only else 1.0
    return {"n": n, "counts": [both, a_only, b_only, neither],
            "difference": (a_only - b_only) / n,
            "ci95": np.quantile(effects, [0.025, 0.975]).tolist(), "p_exact": p,
            "resamples": resamples, "seed": seed, "multiplicity_adjustment": "none"}


def label_metrics(tp: int, fp: int, fn: int) -> dict:
    if min(tp, fp, fn) < 0:
        raise ValueError("counts must be nonnegative")
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "precision_ci95": wilson(tp, tp + fp), "recall_ci95": wilson(tp, tp + fn)}


def cluster_ratio(numerators, denominators, *, resamples=20000, seed=2026) -> dict:
    x, y = np.asarray(numerators, float), np.asarray(denominators, float)
    if x.ndim != 1 or x.shape != y.shape or not len(x) or np.any(x < 0) or np.any(y < x):
        raise ValueError("one numerator/denominator pair per report is required")
    rng, draws = np.random.default_rng(seed), []
    for _ in range(resamples):
        indices = rng.integers(0, len(x), len(x))
        denominator = y[indices].sum()
        if denominator:
            draws.append(float(x[indices].sum() / denominator))
    return {"reports": len(x), "estimate": float(x.sum() / y.sum()) if y.sum() else None,
            "ci95": np.quantile(draws, [0.025, 0.975]).tolist() if draws else None,
            "valid_resamples": len(draws), "resamples": resamples}


def crossed_reader(rows: list[dict], reference: str, comparison: str, *,
                   resamples: int = 20000, seed: int = 2026) -> dict:
    readers = sorted({row["reader_id"] for row in rows})
    cases = sorted({row["case_id"] for row in rows})
    if not readers or not cases or reference == comparison:
        raise ValueError("distinct conditions and nonempty crossed data are required")
    lookup = {}
    for row in rows:
        key = (row["reader_id"], row["case_id"], row["condition"])
        if key in lookup:
            raise ValueError("duplicate reader/case/condition record")
        lookup[key] = row
    quality = np.full((len(readers), len(cases)), np.nan)
    seconds = quality.copy()
    for i, reader in enumerate(readers):
        for j, case in enumerate(cases):
            a = lookup.get((reader, case, comparison))
            b = lookup.get((reader, case, reference))
            if a is None or b is None:
                continue
            qa, qb = a.get("acceptable"), b.get("acceptable")
            if qa is not None and qb is not None:
                if type(qa) is not bool or type(qb) is not bool:
                    raise ValueError("reader acceptability must be boolean or null")
                quality[i, j] = int(qa) - int(qb)
            ta, tb = a.get("active_seconds"), b.get("active_seconds")
            if ta is not None and tb is not None:
                if not np.isfinite([ta, tb]).all() or min(ta, tb) < 0:
                    raise ValueError("time must be finite, nonnegative or null")
                seconds[i, j] = ta - tb
    rng = np.random.default_rng(seed)
    qdraw, tdraw = [], []
    for _ in range(resamples):
        r = rng.integers(0, len(readers), len(readers))
        c = rng.integers(0, len(cases), len(cases))
        q, t = quality[np.ix_(r, c)], seconds[np.ix_(r, c)]
        if np.isfinite(q).any():
            qdraw.append(float(np.nanmean(q)))
        if np.isfinite(t).any():
            tdraw.append(float(np.nanmedian(t)))
    return {"reference": reference, "comparison": comparison, "readers": len(readers),
            "cases": len(cases), "quality_pairs": int(np.isfinite(quality).sum()),
            "time_pairs": int(np.isfinite(seconds).sum()),
            "quality_difference": float(np.nanmean(quality)) if np.isfinite(quality).any() else None,
            "time_difference": float(np.nanmedian(seconds)) if np.isfinite(seconds).any() else None,
            "quality_ci95": np.quantile(qdraw, [0.025, 0.975]).tolist() if qdraw else None,
            "time_ci95": np.quantile(tdraw, [0.025, 0.975]).tolist() if tdraw else None,
            "quality_valid_resamples": len(qdraw), "time_valid_resamples": len(tdraw),
            "resamples": resamples, "seed": seed}


def ordinal_paired(matrix, *, resamples=20000, seed=2026) -> dict:
    counts = np.asarray(matrix, dtype=float)
    if counts.shape != (5, 5) or not np.isfinite(counts).all() or np.any(counts < 0) or not np.equal(counts, np.floor(counts)).all():
        raise ValueError("a 5x5 nonnegative integer table, rows B and columns A, is required")
    n = int(counts.sum())
    if n < 2:
        raise ValueError("at least two paired grades are required")
    grades = np.arange(1, 6)
    a, b = counts.sum(axis=0), counts.sum(axis=1)
    mean_a, mean_b = float(a @ grades / n), float(b @ grades / n)
    differences = (grades[None, :] - grades[:, None]).ravel()
    draws = np.random.default_rng(seed).multinomial(n, counts.ravel() / n, resamples)
    change = draws @ differences / n
    higher, lower, tied = int(np.triu(counts, 1).sum()), int(np.tril(counts, -1).sum()), int(np.trace(counts))
    return {"reports": n, "mean_A": mean_a, "mean_B": mean_b,
            "sd_A": float(np.sqrt(a @ ((grades - mean_a) ** 2) / (n - 1))),
            "sd_B": float(np.sqrt(b @ ((grades - mean_b) ** 2) / (n - 1))),
            "mean_difference": mean_a - mean_b,
            "mean_difference_ci95": np.quantile(change, [0.025, 0.975]).tolist(),
            "A_higher": higher, "A_lower": lower, "tied": tied,
            "sign_test_p": float(binomtest(higher, higher + lower).pvalue) if higher + lower else 1.0,
            "sign_test_estimand": "direction of grade change, not arithmetic mean equality"}


def rater_agreement(ratings, *, resamples=20000, seed=2026) -> dict:
    values = np.asarray(ratings)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2 or not np.isin(values, [0, 1]).all():
        raise ValueError("complete binary pre-consensus ratings are required, rows reports, columns raters")
    n, raters = values.shape

    def fleiss(data):
        positive = data.sum(axis=1)
        observed = np.mean((positive * (positive - 1) +
                            (raters - positive) * (raters - positive - 1)) / (raters * (raters - 1)))
        p = data.mean()
        expected = p * p + (1 - p) ** 2
        return float((observed - expected) / (1 - expected)) if expected < 1 else None

    pairwise = {}
    for i in range(raters):
        for j in range(i + 1, raters):
            observed = np.mean(values[:, i] == values[:, j])
            p, q = values[:, i].mean(), values[:, j].mean()
            expected = p * q + (1 - p) * (1 - q)
            pairwise[f"{i + 1}-{j + 1}"] = float((observed - expected) / (1 - expected)) if expected < 1 else None
    rng = np.random.default_rng(seed)
    draws = [fleiss(values[rng.integers(0, n, n)]) for _ in range(resamples)]
    finite = [value for value in draws if value is not None]
    return {"reports": n, "raters": raters, "fleiss_kappa": fleiss(values),
            "fleiss_ci95": np.quantile(finite, [0.025, 0.975]).tolist() if finite else None,
            "valid_resamples": len(finite), "cohen_pairwise": pairwise,
            "unanimous_fraction": float(np.mean(np.all(values == values[:, :1], axis=1)))}
