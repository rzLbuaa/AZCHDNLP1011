import argparse
import json
from pathlib import Path

from achdnlp.io import atomic_json
from achdnlp.statistics import crossed_reader, ordinal_paired, rater_agreement


def main():
    parser = argparse.ArgumentParser(description="Analyze externally collected clinical annotations")
    parser.add_argument("kind", choices=["reader", "grades", "agreement"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", default="unassisted")
    parser.add_argument("--comparison", default="verified")
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    kwargs = {"resamples": args.resamples, "seed": args.seed}
    if args.kind == "reader":
        result = crossed_reader(data, args.reference, args.comparison, **kwargs)
    elif args.kind == "grades":
        result = ordinal_paired(data, **kwargs)
    else:
        result = rater_agreement(data, **kwargs)
    atomic_json(args.output, result)


if __name__ == "__main__":
    main()
