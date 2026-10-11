from collections import defaultdict

from .schema import CaseResult, ClinicalReference
from .statistics import label_metrics, paired_binary, wilson


def diagnostic_hits(result: CaseResult, reference: ClinicalReference | None):
    if result.status == "technical_failure":
        return 0, 0
    if reference is None or reference.diagnoses is None:
        return None, None
    labels = set(reference.diagnoses)
    ordered = sorted((c for c in result.predictions if c.state not in {"internal", "historical", "rejected"}),
                     key=lambda c: c.order)
    if not ordered:
        return 0, 0
    first = ordered[0]
    lead = (None if first.concept_id is None else
            int(first.state == "definite" and first.temporal == "current" and
                first.polarity == "affirmative" and first.concept_id in labels))
    any_hit = int(any(c.state == "definite" and c.concept_id in labels and
                      c.temporal == "current" and c.polarity == "affirmative" for c in ordered))
    if not any_hit and any(c.concept_id is None for c in ordered):
        any_hit = None
    return lead, any_hit


def rate(values: list[int | None]) -> dict:
    observed = [value for value in values if value is not None]
    hits, missing, n = sum(observed), len(values) - len(observed), len(values)
    return {"hits": hits, "input_n": n, "evaluated_n": len(observed), "unscored_n": missing,
            "available_rate": hits / len(observed) if observed else None,
            "all_input_rate": hits / n if n and not missing else None,
            "available_wilson_ci95": wilson(hits, len(observed)),
            "identification_bounds": [hits / n, (hits + missing) / n] if n else None}


def evaluate(results: list[CaseResult], references: list[ClinicalReference], *,
             resamples: int = 20000, seed: int = 2026) -> dict:
    ref = {item.record_id: item for item in references}
    if len(ref) != len(references):
        raise ValueError("duplicate clinical references")
    grouped = defaultdict(list)
    seen = set()
    for result in results:
        key = (result.record_id, result.arm)
        if key in seen:
            raise ValueError("duplicate report/arm result")
        seen.add(key)
        grouped[result.arm].append(result)
    output = {"arms": {}, "paired_A_B": {}, "data_units": "examination reports",
              "data_kinds": sorted({r.audit.get("data_kind", "unspecified") for r in results})}
    scored = {}
    for arm, records in grouped.items():
        lead, any_hit, acceptable = [], [], []
        family = defaultdict(lambda: [0, 0, 0])
        support_num = support_den = necessary_num = necessary_den = 0
        support_reports = necessity_reports = 0
        for result in records:
            reference = ref.get(result.record_id)
            x, y = diagnostic_hits(result, reference)
            scored[(arm, result.record_id)] = (x, y)
            lead.append(x)
            any_hit.append(y)
            quality = reference.acceptability.get(arm) if reference else None
            acceptable.append(0 if result.status == "technical_failure" else
                              int(quality) if quality is not None else None)
            definite = {c.concept_id for c in result.predictions if result.status == "completed" and c.state == "definite" and c.concept_id
                        and c.temporal == "current" and c.polarity == "affirmative"}
            if reference and reference.diagnoses is not None:
                true = set(reference.diagnoses)
                for code in definite | true:
                    family[code][0] += int(code in definite and code in true)
                    family[code][1] += int(code in definite and code not in true)
                    family[code][2] += int(code not in definite and code in true)
            if result.status == "completed" and reference and reference.supportable is not None:
                support_num += len(definite & set(reference.supportable))
                support_den += len(definite)
                support_reports += 1
            if result.status == "completed" and reference and reference.necessary is not None:
                if reference.supportable is not None and not set(reference.necessary) <= set(reference.supportable):
                    raise ValueError("necessary reference must be a subset of supportable reference")
                necessary_num += len(definite & set(reference.necessary))
                necessary_den += len(set(reference.necessary))
                necessity_reports += 1
        cohorts = {}
        for cohort in sorted({r.cohort for r in records}):
            subset = [r for r in records if r.cohort == cohort]
            pairs = [diagnostic_hits(r, ref.get(r.record_id)) for r in subset]
            cohorts[cohort] = {"leading": rate([p[0] for p in pairs]),
                               "any": rate([p[1] for p in pairs])}
        output["arms"][arm] = {
            "completion": rate([int(r.status == "completed") for r in records]),
            "leading": rate(lead), "any": rate(any_hit), "whole_report_acceptability": rate(acceptable),
            "support_precision": {"numerator": support_num, "denominator": support_den,
                                   "reports": support_reports,
                                   "estimate": support_num / support_den if support_den else None},
            "necessary_retention": {"numerator": necessary_num, "denominator": necessary_den,
                                     "reports": necessity_reports,
                                     "estimate": necessary_num / necessary_den if necessary_den else None},
            "labels": {code: label_metrics(*values) for code, values in sorted(family.items())},
            "cohorts": cohorts,
        }
    if "A" in grouped and "B" in grouped:
        a = {r.record_id: r for r in grouped["A"]}
        b = {r.record_id: r for r in grouped["B"]}
        if a.keys() != b.keys():
            raise ValueError("A/B input sets differ; report missing records rather than silently intersecting")
        for record_id in a:
            if not a[record_id].audit.get("query_hash") or a[record_id].audit.get("query_hash") != b[record_id].audit.get("query_hash"):
                raise ValueError("A/B query fingerprints differ")
        for name, column in (("leading", 0), ("any", 1)):
            counts = [0, 0, 0, 0]
            missing = 0
            for key in sorted(a):
                x, y = scored[("A", key)][column], scored[("B", key)][column]
                if x is None or y is None:
                    missing += 1
                else:
                    counts[{(1, 1): 0, (1, 0): 1, (0, 1): 2, (0, 0): 3}[(x, y)]] += 1
            output["paired_A_B"][name] = paired_binary(counts, resamples=resamples, seed=seed)
            output["paired_A_B"][name]["unscored_pairs"] = missing
            output["paired_A_B"][name]["input_pairs"] = len(a)
    return output
